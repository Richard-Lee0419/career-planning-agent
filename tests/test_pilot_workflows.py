"""Cross-domain API journeys with real persistence and a controlled external model.

These checks validate data flow, provenance boundaries and privacy. They do not
measure the quality of AI advice or employment outcomes.
"""

import importlib
import copy
import json
import os
import secrets
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import test_batch1 as fixtures
from core.standards import load_pilot_dataset
from scripts.seed_pilot_standards import seed_pilot_standards


class PilotWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from core import database
        from models.db_models import Base

        cls.temp = tempfile.TemporaryDirectory()
        os.environ["JWT_SECRET_KEY"] = secrets.token_urlsafe(48)
        os.environ["ZHIPUAI_API_KEY"] = "isolated-test-key"
        cls.original_database = (database.engine, database.SessionLocal, database.DB_PATH)
        database.DB_PATH = str(Path(cls.temp.name) / "pilot-workflows.db")
        database.engine = create_engine(
            f"sqlite:///{database.DB_PATH}", connect_args={"check_same_thread": False}
        )
        database.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=database.engine
        )
        Base.metadata.create_all(bind=database.engine)
        cls.main = importlib.import_module("main")
        cls.original_ai_client = cls.main.client
        cls.client = TestClient(cls.main.app)
        cls.tokens = []
        for username in ("pilot_one", "pilot_two"):
            registered = cls.client.post("/api/auth/register", json={
                "username": username, "password": "TestPass123!"
            })
            assert registered.status_code == 200, registered.text
            login = cls.client.post("/api/auth/login", data={
                "username": username, "password": "TestPass123!"
            })
            assert login.status_code == 200, login.text
            cls.tokens.append(login.json()["access_token"])
        cls.package = load_pilot_dataset()

    @classmethod
    def tearDownClass(cls):
        from core import database

        cls.main.client = cls.original_ai_client
        cls.client.close()
        database.engine.dispose()
        database.engine, database.SessionLocal, database.DB_PATH = cls.original_database
        cls.temp.cleanup()

    auth = fixtures.Batch1ApiTests.auth
    fake_model = fixtures.Batch1ApiTests.fake_model

    def setUp(self):
        from core.database import SessionLocal
        from models.db_models import (
            DBChatMessage, DBChatSession, DBJobStandardMetadata, DBJobStandardProfile,
            DBRoadmap, DBUserProfile,
        )

        previous = {user_id: self.main._ai_attempts.pop(user_id, None) for user_id in (1, 2)}

        def restore_limits():
            for user_id, bucket in previous.items():
                self.main._ai_attempts.pop(user_id, None)
                if bucket is not None:
                    self.main._ai_attempts[user_id] = bucket

        self.addCleanup(restore_limits)
        with SessionLocal() as db:
            for model in (DBChatMessage, DBChatSession, DBRoadmap, DBUserProfile,
                          DBJobStandardMetadata, DBJobStandardProfile):
                db.query(model).delete()
            db.commit()

    def import_pilot(self):
        from core.database import SessionLocal

        with SessionLocal() as db:
            seed_pilot_standards(db)

    @staticmethod
    def encoded(value):
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def plan(role, task):
        return {"summary": f"围绕{role}完成可核验练习", "milestones": [{
            "phase": "岗位实践", "period": "第 1 周", "focus_targets": [task],
            "recommended_resources": ["查阅本岗位来源说明并记录适用限制"],
        }], "conclusion": "结合具体招聘要求核对，不把练习等同于录用能力"}

    @staticmethod
    def pilot_task(action, hours=2, target="内容策划"):
        return {"target_skill": target, "action": action, "deliverable": "一页练习记录",
                "self_check": "逐项核对来源要求并标注未完成项", "estimated_hours": hours}

    @classmethod
    def pilot_plan(cls, role, task, hours=2):
        return {"summary": f"围绕{role}完成可核验练习", "milestones": [{
            "phase": "岗位实践", "weeks": 1, "focus_targets": [cls.pilot_task(task, hours,
                {"招聘助理": "岗位需求分析", "市场助理": "市场调研"}.get(role, "内容策划"))],
            "recommended_resources": [],
        }], "conclusion": "结合具体招聘要求核对，不把练习等同于录用能力"}

    @staticmethod
    def rendered_task(task):
        hours = task["estimated_hours"]
        duration = f"预计{hours:g}小时" if hours is not None else "耗时待确认"
        return f"能力：{task['target_skill']}；{task['action']}；产出：{task['deliverable']}；自查：{task['self_check']}；{duration}"

    @staticmethod
    def assessment(role, skills, major="工商管理"):
        return {"name": "合成测试学生", "education_level": "本科", "major": major,
            "current_skills": skills, "soft_skills": ["团队合作"], "interests": [],
            "target_roles": [role], "weekly_learning_time": "每周 6 小时"}

    def save_assessment(self, assessment, index=0):
        self.fake_model(self.encoded({"major": "错误的计算机专业", "current_skills": ["Python"],
                                      "target_roles": ["前端工程师"]}))
        response = self.client.post("/api/user/profile/extract", headers=self.auth(index), json={
            "resume_text": "以下问卷内容为合成测试事实。", "assessment": assessment
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["profile"]["major"], assessment["major"])
        self.assertEqual(response.json()["profile"]["target_roles"], assessment["target_roles"])
        return response

    def create_path(self, role, task, index=0):
        plan = (self.pilot_plan(role, task) if any(item.role_name == role for item in self.package.roles)
                else self.plan(role, task))
        fake = self.fake_model(self.encoded(plan), self.encoded({"revised_roadmap": plan}))
        response = self.client.post("/api/agent/learning-path", params={"target_role": role},
                                    headers=self.auth(index))
        self.assertEqual(response.status_code, 200, response.text)
        return response.json(), fake

    def test_catalog_exposes_imported_roles_and_their_actual_source_state(self):
        from core.database import SessionLocal
        from models.db_models import DBJobStandardProfile

        with SessionLocal() as db:
            db.add_all([
                DBJobStandardProfile(role_name="前端开发工程师", description="演示用岗位标准：公开示例",
                                     core_skills='["React"]', soft_skills="[]", certifications="[]"),
                DBJobStandardProfile(role_name="未知领域助理", description="未追溯的旧标准",
                                     core_skills='["资料整理"]', soft_skills="[]", certifications="[]"),
            ])
            db.commit()
        initial = self.client.get("/api/career/catalog")
        self.assertEqual(initial.status_code, 200, initial.text)
        roles = {role["role_name"]: role for role in initial.json()["roles"]}
        self.assertEqual(set(roles), {"前端开发工程师", "未知领域助理"})
        self.assertEqual(roles["前端开发工程师"]["standard_source"]["type"], "demo_example")
        self.assertEqual(roles["未知领域助理"]["domain"], "unclassified")
        self.import_pilot()
        catalog = self.client.get("/api/career/catalog").json()
        roles = {role["role_name"]: role for role in catalog["roles"]}
        self.assertEqual(set(roles), {role.role_name for role in self.package.roles} |
                         {"前端开发工程师", "未知领域助理"})
        for expected in self.package.roles:
            actual = roles[expected.role_name]
            self.assertEqual(actual["role_id"], expected.role_id)
            self.assertEqual(actual["domain"], expected.domain)
            self.assertEqual(actual["core_skills"], expected.core_skills)
            self.assertEqual(actual["standard_source"]["version"], self.package.version)
            self.assertEqual(actual["standard_source"]["review_status"], "source_checked")
            self.assertEqual(actual["standard_source"]["sources"][0]["evidence_location"],
                             expected.standard_source.sources[0].evidence_location)
        self.assertEqual({domain["id"] for domain in catalog["domains"]},
                         {"technology", "unclassified", "marketing_content", "human_resources"})

    def run_journey(self, role, domain, skills, matched, missing, task, major):
        self.import_pilot()
        self.save_assessment(self.assessment(role, skills, major))
        recommended = self.client.get("/api/recommendations", params={"domain": domain}, headers=self.auth())
        self.assertEqual(recommended.status_code, 200, recommended.text)
        self.assertTrue(all(item["domain"] == domain for item in recommended.json()["data"]))
        match = next(item for item in recommended.json()["data"] if item["role_name"] == role)
        self.assertEqual(set(match["matched_skills"]), set(matched))
        self.assertIn(missing, match["missing_skills"])
        self.assertIsNotNone(match["score"])
        self.assertEqual(match["standard_source"]["version"], self.package.version)
        other_domain = "human_resources" if domain == "marketing_content" else "marketing_content"
        other = self.client.get("/api/recommendations", params={"domain": other_domain}, headers=self.auth())
        self.assertTrue(all(item["domain"] == other_domain for item in other.json()["data"]))
        self.assertNotIn(role, [item["role_name"] for item in other.json()["data"]])

        gap_payload = {key: {"score": 50, "analysis": "基于填报能力解释差距", "suggestions": [task]}
                       for key in ("basic", "skill", "soft", "potential")}
        gap_payload.update(immediate_next_steps=[task], roadmap_preview=f"针对{role}练习")
        gap_fake = self.fake_model(self.encoded(gap_payload))
        gap = self.client.post("/api/agent/gap-analysis", params={"target_role": role}, headers=self.auth())
        self.assertEqual(gap.status_code, 200, gap.text)
        self.assertEqual(gap.json()["overall_match_score"], match["score"])
        self.assertEqual(gap.json()["matched_requirements"], match["matched_skills"])
        self.assertEqual(gap.json()["standard_source"]["version"], self.package.version)
        self.assertIn(role, gap_fake.calls[0]["messages"][1]["content"])

        path, path_fake = self.create_path(role, task)
        self.assertEqual(path["target_role"], role)
        rendered = self.rendered_task(self.pilot_plan(role, task)["milestones"][0]["focus_targets"][0])
        self.assertEqual(path["milestones"][0]["focus_targets"], [rendered])
        self.assertEqual(path["milestones"][0]["period"], "第1周")
        self.assertEqual(path["standard_source"]["version"], self.package.version)
        for call in path_fake.calls:
            self.assertIn(role, call["messages"][1]["content"])
            self.assertIn(major, call["messages"][1]["content"])
            self.assertNotIn("错误的计算机专业", call["messages"][1]["content"])
            self.assertIn(self.package.version, call["messages"][1]["content"])
        task_key = f"岗位实践::{rendered}"
        progress = self.client.put(f"/api/history/roadmaps/{path['id']}/progress", headers=self.auth(),
                                   json={"completed_tasks": [task_key]})
        self.assertEqual(progress.status_code, 200, progress.text)
        restored = self.client.get(f"/api/history/roadmaps/{path['id']}", headers=self.auth())
        self.assertEqual(restored.json()["completed_tasks"], [task_key])
        self.assertEqual(restored.json()["standard_source"], path["standard_source"])
        chat_id = self.client.post("/api/chat/sessions", headers=self.auth(), json={
            "target_role": role, "roadmap_id": path["id"]
        }).json()["id"]
        chat_fake = self.fake_model(f"根据{role}当前进度，先复核练习记录")
        chat = self.client.post("/api/agent/chat", headers=self.auth(), json={
            "session_id": chat_id, "message": "根据已完成任务给我下一步建议"
        })
        self.assertEqual(chat.status_code, 200, chat.text)
        context = chat_fake.calls[0]["messages"][0]["content"]
        self.assertIn(task_key, context)
        self.assertIn(role, context)
        self.assertIn(self.package.version, context)
        saved_chat = self.client.get(f"/api/chat/sessions/{chat_id}", headers=self.auth()).json()
        self.assertEqual(saved_chat["roadmap_id"], path["id"])
        self.assertIn(role, saved_chat["messages"][-1]["content"])
        report = self.client.post("/api/report/export", params={"roadmap_id": path["id"]}, headers=self.auth())
        self.assertEqual(report.status_code, 200, report.text)
        self.assertIn(f"- 目标岗位：{role}", report.text)
        self.assertIn(f"[x] {rendered}", report.text)
        self.assertIn(self.package.version, report.text)
        self.assertIn("仅表示来源核对", report.text)
        self.assertIn(major, report.text)
        self.assertNotIn("错误的计算机专业", report.text)

    def test_marketing_assessment_to_saved_export_preserves_role_and_evidence(self):
        self.run_journey("市场助理", "marketing_content", ["文案撰写", "Excel"],
            ["文案写作", "电子表格"], "市场调研", "整理三条市场信息并制作活动反馈表", "市场营销")

    def test_hr_assessment_to_saved_export_preserves_role_and_evidence(self):
        self.run_journey("招聘助理", "human_resources", ["简历初筛", "面试安排", "Excel"],
            ["简历筛选", "面试协调", "电子表格"], "岗位需求分析", "整理合成简历筛选表和面试排期", "人力资源管理")

    def test_missing_abilities_return_null_and_gap_does_not_call_model(self):
        self.import_pilot()
        assessment = self.assessment("招聘助理", [])
        assessment["soft_skills"] = []
        self.save_assessment(assessment)
        matches = self.client.get("/api/recommendations", params={"domain": "human_resources"},
                                  headers=self.auth()).json()["data"]
        self.assertTrue(matches)
        self.assertTrue(all(item["score"] is None for item in matches))
        fake = self.fake_model()
        response = self.client.post("/api/agent/gap-analysis", params={"target_role": "招聘助理"},
                                    headers=self.auth())
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(fake.calls, [])

    def test_modified_standard_loses_score_and_blocks_new_gap_and_path(self):
        from core.database import SessionLocal
        from models.db_models import DBJobStandardProfile

        self.import_pilot()
        self.save_assessment(self.assessment("招聘助理", ["简历筛选"]))
        with SessionLocal() as db:
            standard = db.query(DBJobStandardProfile).filter_by(role_name="招聘助理").one()
            standard.core_skills = self.encoded(["来源审核之后追加的能力"])
            db.commit()
        match = next(item for item in self.client.get("/api/recommendations",
            params={"domain": "human_resources"}, headers=self.auth()).json()["data"]
            if item["role_name"] == "招聘助理")
        self.assertIsNone(match["score"])
        self.assertEqual(match["standard_source"]["review_status"], "modified_unverified")
        self.assertTrue(match["standard_source"]["sources"])
        fake = self.fake_model()
        for endpoint in ("gap-analysis", "learning-path"):
            result = self.client.post(f"/api/agent/{endpoint}", params={"target_role": "招聘助理"},
                                      headers=self.auth())
            self.assertEqual(result.status_code, 422, result.text)
        self.assertEqual(fake.calls, [])

    def test_unknown_role_can_be_explored_without_claiming_reviewed_requirements(self):
        from core.database import SessionLocal
        from models.db_models import DBJobStandardProfile

        with SessionLocal() as db:
            db.add(DBJobStandardProfile(role_name="未分类探测岗", description="未追溯来源的旧标准",
                core_skills='["资料整理"]', soft_skills="[]", certifications="[]"))
            db.commit()
        for role in ("暂无标准职业探索", "未分类探测岗"):
            with self.subTest(role=role):
                self.save_assessment(self.assessment(role, ["资料整理"]))
                path, fake = self.create_path(role, "收集两条公开信息并先核实目标岗位任务")
                self.assertTrue("探索" in path["standard_notice"] or "未核实" in path["standard_notice"])
                self.assertNotIn("试点只经过来源核对", path["standard_notice"])
                self.assertIn(path["standard_notice"], fake.calls[0]["messages"][1]["content"])
                if role == "暂无标准职业探索":
                    self.assertIsNone(path["standard_source"])
                else:
                    matches = self.client.get("/api/recommendations", params={"domain": "unclassified"},
                                               headers=self.auth()).json()["data"]
                    self.assertEqual(matches[0]["role_name"], role)
                    self.assertIsNone(matches[0]["score"])
                    self.assertEqual(path["standard_source"]["review_status"], "unverified")

    def test_history_keeps_source_snapshot_and_other_users_cannot_read_or_change_it(self):
        from core.database import SessionLocal
        from models.db_models import DBJobStandardMetadata, DBJobStandardProfile, DBUserProfile

        self.import_pilot()
        self.save_assessment(self.assessment("市场助理", ["Excel"], "原市场营销专业"))
        path, _ = self.create_path("市场助理", "保留原版本的活动反馈表练习")
        original_source = path["standard_source"]
        with SessionLocal() as db:
            standard = db.query(DBJobStandardProfile).filter_by(role_name="市场助理").one()
            standard.description += "；修改后追加的角色解释"
            metadata = db.get(DBJobStandardMetadata, standard.id)
            value = json.loads(metadata.metadata_json)
            value["standard_source"]["version"] = "changed-after-save-v2"
            metadata.metadata_json = self.encoded(value)
            profile = db.query(DBUserProfile).filter_by(user_id=1).one()
            profile.major = "后来修改的专业"
            db.commit()
        self.save_assessment(self.assessment("招聘助理", ["面试安排"], "第二用户专属专业"), index=1)
        fake = self.fake_model()
        restored = self.client.get(f"/api/history/roadmaps/{path['id']}", headers=self.auth())
        self.assertEqual(restored.status_code, 200, restored.text)
        self.assertEqual(restored.json()["standard_source"], original_source)
        self.assertEqual(restored.json()["standard_source"]["review_status"], "source_checked")
        report = self.client.post("/api/report/export", params={"roadmap_id": path["id"]}, headers=self.auth())
        self.assertEqual(report.status_code, 200, report.text)
        self.assertIn(original_source["version"], report.text)
        self.assertIn("原市场营销专业", report.text)
        self.assertNotIn("changed-after-save-v2", report.text)
        self.assertNotIn("后来修改的专业", report.text)
        self.assertNotIn("第二用户专属专业", report.text)
        self.assertEqual(self.client.get(f"/api/history/roadmaps/{path['id']}", headers=self.auth(1)).status_code, 404)
        self.assertEqual(self.client.put(f"/api/history/roadmaps/{path['id']}/progress", headers=self.auth(1),
            json={"completed_tasks": []}).status_code, 404)
        self.assertEqual(self.client.post("/api/report/export", params={"roadmap_id": path["id"]},
            headers=self.auth(1)).status_code, 404)
        self.assertEqual(self.client.post("/api/chat/sessions", headers=self.auth(1), json={
            "target_role": "市场助理", "roadmap_id": path["id"]}).status_code, 404)
        self.assertEqual(fake.calls, [])

    def test_long_advisor_context_keeps_current_and_historical_source_boundaries(self):
        from core.database import SessionLocal
        from models.db_models import DBJobStandardMetadata, DBJobStandardProfile, DBRoadmap, DBUserProfile

        self.import_pilot()
        self.save_assessment(self.assessment("市场助理", ["Excel"]))
        path, _ = self.create_path("市场助理", "保留旧版本市场材料")
        with SessionLocal() as db:
            standard = db.query(DBJobStandardProfile).filter_by(role_name="市场助理").one()
            standard.core_skills = self.encoded(["来源审核后改动的能力"])
            metadata = db.get(DBJobStandardMetadata, standard.id)
            value = json.loads(metadata.metadata_json)
            value["standard_source"]["version"] = "current-source-v2"
            metadata.metadata_json = self.encoded(value)
            profile = db.query(DBUserProfile).filter_by(user_id=1).one()
            long_list = self.encoded([f"合成第{number}项资料" * 40 for number in range(20)])
            for field in ("current_skills", "soft_skills", "certificates", "interests", "target_roles"):
                setattr(profile, field, long_list)
            for field in ("education_level", "major", "grade", "location",
                          "internship_experience", "weekly_learning_time"):
                setattr(profile, field, "合成长文本" * 100)
            legacy = DBRoadmap(user_id=1, role_name="市场助理",
                roadmap_json=self.encoded(self.plan("市场助理", "旧路径未记录来源的练习")),
                progress_json="[]")
            db.add(legacy)
            db.commit()
            legacy_id = legacy.id
        fake = self.fake_model("先复核当前标准，区分已保存路径依据", "旧路径来源缺失，请自行核对")
        for roadmap_id in (path["id"], legacy_id):
            session = self.client.post("/api/chat/sessions", headers=self.auth(), json={
                "target_role": "市场助理", "roadmap_id": roadmap_id
            })
            self.assertEqual(session.status_code, 200, session.text)
            response = self.client.post("/api/agent/chat", headers=self.auth(), json={
                "session_id": session.json()["id"], "message": "根据已保存版本建议下一步"
            })
            self.assertEqual(response.status_code, 200, response.text)
        contexts = [json.loads(call["messages"][0]["content"].splitlines()[-1]) for call in fake.calls]
        for context in contexts:
            self.assertLessEqual(len(self.encoded(context)), 4500)
            self.assertLessEqual(len(context["profile"]["current_skills"]), 3)
            self.assertEqual(context["standard_source"]["version"], "current-source-v2")
            self.assertEqual(context["standard_source"]["review_status"], "modified_unverified")
        historical = contexts[0]["current_roadmap"]
        self.assertEqual(historical["id"], path["id"])
        self.assertEqual(historical["standard_source"]["version"], self.package.version)
        self.assertEqual(historical["standard_source"]["review_status"], "source_checked")
        missing_source = contexts[1]["current_roadmap"]
        self.assertEqual(missing_source["id"], legacy_id)
        self.assertIsNone(missing_source["standard_source"])
        self.assertIn("旧路径未保存标准来源", missing_source["standard_notice"])

    def test_structurally_valid_pilot_path_with_unverified_credential_is_not_saved(self):
        from core.database import SessionLocal
        from models.db_models import DBRoadmap

        self.import_pilot()
        self.save_assessment(self.assessment("内容运营", ["文案撰写"]))
        draft = self.pilot_plan("内容运营", "编写一篇练习稿并检查是否符合选题要求")
        critic = self.pilot_plan("内容运营", "内容运营专家认证准备")
        fake = self.fake_model(self.encoded(draft), self.encoded({"revised_roadmap": critic}), self.encoded(critic))
        response = self.client.post("/api/agent/learning-path", params={"target_role": "内容运营"},
                                    headers=self.auth())
        self.assertEqual(response.status_code, 502, response.text)
        self.assertEqual(len(fake.calls), 3)
        with SessionLocal() as db:
            self.assertEqual(db.query(DBRoadmap).count(), 0)

    def test_pilot_resources_keep_only_checked_links_with_canonical_titles(self):
        from core.database import SessionLocal
        from scripts.seed_demo_data import seed_demo_standards

        self.import_pilot()
        self.save_assessment(self.assessment("内容运营", ["文案撰写"]))
        source = next(role for role in self.package.roles if role.role_name == "内容运营").standard_source.sources[0]
        task = "为合成活动编写选题说明，产出一页文案并逐条自查，预计 2 小时"
        plan = self.pilot_plan("内容运营", task)
        plan["milestones"][0]["recommended_resources"] = [
            "内容运营专家认证备考教材", "虚构资料：https://invalid.example/fake-certificate",
            f"错误的教材名称包装（{source.url}）",
            {"title": "模型返回对象且标题不可信", "url": str(source.url)},
            {"title": "未核实的模型资源对象", "url": "https://invalid.example/object"},
        ]
        plan["milestones"].append({"phase": "反馈整理", "weeks": 1,
            "focus_targets": [self.pilot_task("整理三条合成反馈并修订练习稿")],
            "recommended_resources": ["无来源的认证课程", "https://invalid.example/course"],
        })
        self.fake_model(self.encoded(plan), self.encoded({"revised_roadmap": plan}))
        response = self.client.post("/api/agent/learning-path", params={"target_role": "内容运营"},
                                    headers=self.auth())
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        expected_resources = [f"岗位背景参考（非学习教程）—{source.title}：{source.url}"]
        self.assertEqual(result["milestones"][0]["focus_targets"], [self.rendered_task(self.pilot_task(task))])
        self.assertEqual([stage["period"] for stage in result["milestones"]], ["第1周", "第2周"])
        self.assertEqual(result["milestones"][0]["recommended_resources"], expected_resources)
        self.assertEqual(result["milestones"][1]["recommended_resources"], [])
        restored = self.client.get(f"/api/history/roadmaps/{result['id']}", headers=self.auth()).json()
        self.assertEqual(restored["milestones"][0]["recommended_resources"], expected_resources)
        report = self.client.post("/api/report/export", params={"roadmap_id": result["id"]}, headers=self.auth())
        self.assertEqual(report.status_code, 200, report.text)
        self.assertIn(expected_resources[0], report.text)
        self.assertNotIn("invalid.example", report.text)
        self.assertNotIn("专家认证备考", report.text)
        self.assertNotIn("错误的教材名称", report.text)

        # The narrow pilot safeguard must not silently change existing demo behavior.
        with SessionLocal() as db:
            seed_demo_standards(db)
        self.save_assessment(self.assessment("前端开发工程师", ["React"], "软件工程"))
        demo, _ = self.create_path("前端开发工程师", "准备旧示例认证练习")
        self.assertEqual(demo["standard_source"]["type"], "demo_example")
        self.assertEqual(demo["milestones"][0]["focus_targets"], ["准备旧示例认证练习"])

    def test_incomplete_tasks_or_unachievable_pilot_time_budgets_are_not_saved(self):
        from core.database import SessionLocal
        from models.db_models import DBRoadmap

        self.import_pilot()
        self.save_assessment(self.assessment("内容运营", ["文案撰写"]))
        valid = self.pilot_plan("内容运营", "编写选题说明")
        cases = []
        for field in ("deliverable", "self_check", "estimated_hours"):
            missing = copy.deepcopy(valid)
            del missing["milestones"][0]["focus_targets"][0][field]
            cases.append((f"missing {field}", missing, "每周 6 小时"))
        for field in ("action", "deliverable", "self_check"):
            blank = copy.deepcopy(valid)
            blank["milestones"][0]["focus_targets"][0][field] = " \t "
            cases.append((f"blank {field}", blank, "每周 6 小时"))
        over_budget = copy.deepcopy(valid)
        over_budget["milestones"][0]["focus_targets"] = [
            self.pilot_task("编写选题说明", 4), self.pilot_task("修订练习稿", 3)
        ]
        cases.append(("two tasks exceed weekly hours", over_budget, "每周 6 小时"))
        no_hours = self.pilot_plan("内容运营", "编写选题说明", None)
        cases.append(("known budget needs estimate", no_hours, "每周 6 小时"))
        too_long = copy.deepcopy(valid)
        too_long["milestones"][0]["weeks"] = 3
        second = copy.deepcopy(too_long["milestones"][0])
        second["phase"] = "第二阶段"
        too_long["milestones"].append(second)
        cases.append(("total weeks exceeds four", too_long, "每周 6 小时"))
        cases.append(("unknown budget must not guess hours", valid, "尚未确定"))
        old_shape = self.plan("内容运营", "标题代替可执行任务")
        cases.append(("legacy strings cannot replace pilot tasks", old_shape, "每周 6 小时"))
        for name, output, weekly_time in cases:
            with self.subTest(case=name):
                with SessionLocal() as db:
                    from models.db_models import DBUserProfile
                    profile = db.query(DBUserProfile).filter_by(user_id=1).one()
                    profile.weekly_learning_time = weekly_time
                    db.commit()
                fake = self.fake_model(self.encoded(valid), self.encoded({"revised_roadmap": output}), self.encoded(output))
                response = self.client.post("/api/agent/learning-path", params={"target_role": "内容运营"},
                                            headers=self.auth())
                self.assertEqual(response.status_code, 502, response.text)
                self.assertEqual(len(fake.calls), 3)
                with SessionLocal() as db:
                    self.assertEqual(db.query(DBRoadmap).count(), 0)

    def test_pilot_rejects_already_matched_or_invented_targets_after_one_repair(self):
        from core.database import SessionLocal
        from models.db_models import DBRoadmap

        self.import_pilot()
        self.save_assessment(self.assessment("内容运营", ["文案撰写", "图文排版"]))
        for target in ("文案写作", "不存在的职业能力"):
            with self.subTest(target=target):
                bad = self.pilot_plan("内容运营", "练习任务")
                bad["milestones"][0]["focus_targets"][0]["target_skill"] = target
                fake = self.fake_model(self.encoded(bad), self.encoded({"revised_roadmap": bad}), self.encoded(bad))
                response = self.client.post("/api/agent/learning-path", params={"target_role": "内容运营"}, headers=self.auth())
                self.assertEqual(response.status_code, 502, response.text)
                self.assertEqual(len(fake.calls), 3)
                with SessionLocal() as db:
                    self.assertEqual(db.query(DBRoadmap).count(), 0)

    def test_one_pilot_repair_recovers_invalid_json_and_saved_retry_is_idempotent(self):
        from core.database import SessionLocal
        from models.db_models import DBRoadmap

        self.import_pilot()
        self.save_assessment(self.assessment("内容运营", ["文案撰写"]))
        valid = self.pilot_plan("内容运营", "为虚构主题整理选题依据")
        fake = self.fake_model(self.encoded(valid), "not JSON", self.encoded(valid))
        headers = {**self.auth(), "Idempotency-Key": "pilot-repair-request-001"}
        response = self.client.post("/api/agent/learning-path", params={"target_role": "内容运营"}, headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["generation_attempts"], 3)
        again = self.client.post("/api/agent/learning-path", params={"target_role": "内容运营"}, headers=headers)
        self.assertEqual(again.json()["id"], response.json()["id"])
        self.assertEqual(len(fake.calls), 3)
        with SessionLocal() as db:
            self.assertEqual(db.query(DBRoadmap).count(), 1)

    def test_advisor_preserves_next_pending_task_of_selected_version_even_when_context_is_reduced(self):
        from core.database import SessionLocal
        from models.db_models import DBRoadmap, DBUserProfile

        self.import_pilot()
        self.save_assessment(self.assessment("内容运营", ["文案撰写"]))
        selected, _ = self.create_path("内容运营", "所选版本第一项")
        self.create_path("内容运营", "其他版本不得替代")
        with SessionLocal() as db:
            record = db.query(DBRoadmap).filter_by(id=selected["id"]).one()
            saved = json.loads(record.roadmap_json)
            saved["milestones"][0]["focus_targets"] = ["已完成任务", "同阶段待完成任务"]
            saved["milestones"].append({"phase": "下一阶段", "period": "第2周",
                "focus_targets": ["不可跳过前一阶段"], "recommended_resources": []})
            record.roadmap_json = self.encoded(saved)
            record.progress_json = self.encoded(["岗位实践::已完成任务"])
            profile = db.query(DBUserProfile).filter_by(user_id=1).one()
            profile.internship_experience = "长经历" * 600
            profile.current_skills = self.encoded(["长技能" * 25 + str(i) for i in range(12)])
            db.commit()
            context = json.loads(self.main.advisor_context(db, 1, "内容运营", record.id))
            self.assertEqual(context["current_roadmap"]["next_pending_task"],
                {"phase": "岗位实践", "task": "同阶段待完成任务"})
            self.assertEqual(context["current_roadmap"]["remaining_task_count"], 2)
            self.assertLessEqual(len(self.encoded(context)), 4500)
            record.progress_json = self.encoded(["岗位实践::已完成任务", "岗位实践::同阶段待完成任务",
                                                  "下一阶段::不可跳过前一阶段"])
            db.commit()
            finished = json.loads(self.main.advisor_context(db, 1, "内容运营", record.id))
            self.assertIsNone(finished["current_roadmap"]["next_pending_task"])
            self.assertEqual(finished["current_roadmap"]["remaining_task_count"], 0)

    def test_unknown_time_budget_uses_null_hours_and_renders_bounded_periods(self):
        self.import_pilot()
        assessment = self.assessment("内容运营", ["文案撰写"])
        assessment["weekly_learning_time"] = "尚未确定"
        self.save_assessment(assessment)
        plan = self.pilot_plan("内容运营", "编写选题说明", None)
        plan["milestones"][0]["weeks"] = 2
        second_task = self.pilot_task("收集合成反馈并修订选题说明", None)
        plan["milestones"].append({"phase": "反馈整理", "weeks": 2,
            "focus_targets": [second_task], "recommended_resources": []})
        fake = self.fake_model(self.encoded(plan), self.encoded({"revised_roadmap": plan}))
        response = self.client.post("/api/agent/learning-path", params={"target_role": "内容运营"},
                                    headers=self.auth())
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual([stage["period"] for stage in result["milestones"]], ["第1–2周", "第3–4周"])
        self.assertEqual(result["milestones"][1]["focus_targets"], [self.rendered_task(second_task)])
        self.assertTrue(all("耗时待确认" in task and "预计" not in task
                            for stage in result["milestones"] for task in stage["focus_targets"]))
        self.assertIn("尚未确定", fake.calls[0]["messages"][1]["content"])
        restored = self.client.get(f"/api/history/roadmaps/{result['id']}", headers=self.auth()).json()
        self.assertEqual(restored["milestones"], result["milestones"])


if __name__ == "__main__":
    unittest.main()
