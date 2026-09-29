"""Batch 1 API checks against an isolated SQLite database and a fake AI client."""

import importlib
import json
import os
import secrets
import sqlite3
import tempfile
import unittest
import uuid
import wave
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker


class FakeModel:
    def __init__(self, *contents):
        self.contents = list(contents)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        content = self.contents.pop(0)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


class Batch1ApiTests(unittest.TestCase):
    @staticmethod
    def wav_bytes():
        buffer = BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(b"\x00" * 3200)
        return buffer.getvalue()

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        os.environ["JWT_SECRET_KEY"] = secrets.token_urlsafe(48)
        os.environ["ZHIPUAI_API_KEY"] = "isolated-test-key"

        from core import database

        cls.original_engine = database.engine
        cls.original_session_local = database.SessionLocal
        cls.original_db_path = database.DB_PATH
        database.DB_PATH = str(Path(cls.temp.name) / "career_project.db")
        database.engine = create_engine(
            f"sqlite:///{database.DB_PATH}", connect_args={"check_same_thread": False}
        )
        database.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=database.engine)

        cls.main = importlib.import_module("main")
        cls.original_ai_client = cls.main.client
        cls.client = TestClient(cls.main.app)
        cls.tokens = []
        for username in ("batch_one", "batch_two"):
            response = cls.client.post(
                "/api/auth/register", json={"username": username, "password": "TestPass123!"}
            )
            assert response.status_code == 200, response.text
            login = cls.client.post(
                "/api/auth/login", data={"username": username, "password": "TestPass123!"}
            )
            assert login.status_code == 200, login.text
            cls.tokens.append(login.json()["access_token"])

    @classmethod
    def tearDownClass(cls):
        cls.main.client = cls.original_ai_client
        cls.client.close()
        from core import database

        database.engine.dispose()
        database.engine = cls.original_engine
        database.SessionLocal = cls.original_session_local
        database.DB_PATH = cls.original_db_path
        cls.temp.cleanup()

    def auth(self, index=0):
        return {"Authorization": f"Bearer {self.tokens[index]}"}

    def fake_model(self, *contents):
        fake = FakeModel(*contents)
        self.main.client = SimpleNamespace(chat=SimpleNamespace(completions=fake))
        return fake

    def seed_batch2_facts(self):
        from core.database import SessionLocal
        from models.db_models import DBJobStandardProfile, DBUserProfile

        with SessionLocal() as db:
            profile = db.query(DBUserProfile).filter(DBUserProfile.user_id == 1).first()
            if not profile:
                profile = DBUserProfile(user_id=1)
                db.add(profile)
            profile.name = "真实用户"
            profile.major = "计算机"
            profile.current_skills = '["React"]'
            profile.soft_skills = '["团队协作"]'
            profile.interests = '["交互设计"]'
            profile.target_roles = '["前端工程师"]'
            profile.weekly_learning_time = "每周 6-10 小时"
            if not db.query(DBJobStandardProfile).filter(DBJobStandardProfile.role_name == "前端开发工程师").first():
                db.add(DBJobStandardProfile(
                    role_name="前端开发工程师", core_skills='["React", "TypeScript", "Git"]',
                    soft_skills='["团队协作"]', certifications='[]', description="前端交互与界面开发"
                ))
            other = db.query(DBUserProfile).filter(DBUserProfile.user_id == 2).first()
            if not other:
                db.add(DBUserProfile(user_id=2, current_skills='["Java"]', soft_skills='[]',
                                     target_roles='["前端工程师"]', interests='[]'))
            db.commit()

    def test_registration_validation_and_login_limit(self):
        invalid = self.client.post("/api/auth/register", json={"username": " ", "password": "short"})
        self.assertEqual(invalid.status_code, 422)
        for _ in range(5):
            result = self.client.post(
                "/api/auth/login", data={"username": "unknown_batch_user", "password": "wrong"}
            )
            self.assertEqual(result.status_code, 400)
        blocked = self.client.post(
            "/api/auth/login", data={"username": "unknown_batch_user", "password": "wrong"}
        )
        self.assertEqual(blocked.status_code, 429)

    def test_job_endpoints_work_without_private_job_dataset(self):
        for path in ("/api/jobs", "/api/jobs/search?keyword=前端", "/api/jobs/stats"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertIsInstance(response.json()["data"], list)

    def test_stt_requires_login_and_rejects_invalid_and_oversized_audio(self):
        wav = self.wav_bytes()
        anonymous = self.client.post("/api/audio/stt", files={"file": ("x.wav", wav, "audio/wav")})
        self.assertEqual(anonymous.status_code, 401)
        invalid = self.client.post(
            "/api/audio/stt", headers=self.auth(),
            files={"file": ("x.wav", b"not-wav", "audio/wav")},
        )
        self.assertEqual(invalid.status_code, 400)
        large = self.client.post(
            "/api/audio/stt", headers=self.auth(),
            files={"file": ("x.wav", wav + b"0" * (10 * 1024 * 1024), "audio/wav")},
        )
        self.assertEqual(large.status_code, 413)

    def test_pdf_rejects_invalid_bytes_without_calling_ai(self):
        response = self.client.post(
            "/api/user/profile/upload-resume", headers=self.auth(),
            files={"file": ("resume.pdf", b"not-a-pdf", "application/pdf")},
        )
        self.assertEqual(response.status_code, 400)

    def test_audio_playback_requires_an_untampered_signed_link(self):
        audio_dir = Path(self.temp.name) / "audio"
        audio_dir.mkdir(exist_ok=True)
        filename = f"gen_q_{uuid.uuid4()}.wav"
        (audio_dir / filename).write_bytes(self.wav_bytes())
        old_audio_dir = self.main.AUDIO_DIR
        self.main.AUDIO_DIR = str(audio_dir)
        try:
            url = self.main.signed_audio_url(filename, 1)
            self.assertEqual(self.client.get(url).status_code, 200)
            self.assertEqual(self.client.get(url.replace("user_id=1", "user_id=2")).status_code, 403)
            self.assertEqual(self.client.get(f"/static/audio/{filename}").status_code, 404)
        finally:
            self.main.AUDIO_DIR = old_audio_dir

    def test_invalid_evaluation_is_not_persisted_and_valid_record_is_user_scoped(self):
        from models.db_models import DBInterview
        from core.database import SessionLocal

        payload = {
            "target_role": "前端工程师", "question": "解释事件循环", "user_answer": "先执行同步任务",
        }
        self.fake_model(json.dumps({
            "score": 200, "evaluation": "test", "improvement_suggestion": "test", "reference_answer": "test"
        }))
        invalid = self.client.post(
            "/api/agent/mock-interview/evaluate", headers=self.auth(), json=payload
        )
        self.assertEqual(invalid.status_code, 502)
        with SessionLocal() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(DBInterview)), 0)

        self.fake_model(json.dumps({
            "score": 72, "evaluation": "结构清楚", "improvement_suggestion": "补充例子",
            "reference_answer": "说明宏任务和微任务"
        }, ensure_ascii=False))
        valid = self.client.post(
            "/api/agent/mock-interview/evaluate", headers=self.auth(), json=payload
        )
        self.assertEqual(valid.status_code, 200, valid.text)
        self.assertEqual(valid.json()["score"], 72)
        mine = self.client.get("/api/history/interviews", headers=self.auth())
        other = self.client.get("/api/history/interviews", headers=self.auth(1))
        self.assertEqual(mine.json()["count"], 1)
        self.assertEqual(other.json()["count"], 0)

    def test_same_session_id_cannot_read_another_users_messages(self):
        fake = self.fake_model("这是第一位用户的回答", "这是第二位用户的回答")
        payload = {"session_id": "shared-session", "message": "请给我建议"}
        first = self.client.post("/api/agent/chat", headers=self.auth(), json=payload)
        second = self.client.post("/api/agent/chat", headers=self.auth(1), json=payload)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(len(fake.calls[1]["messages"]), 2)

    def test_roadmap_rejects_empty_milestones_without_saving(self):
        from core.database import SessionLocal
        from models.db_models import DBRoadmap, DBUserProfile

        with SessionLocal() as db:
            db.add(DBUserProfile(user_id=1, major="计算机", current_skills="[]", certificates="[]"))
            db.commit()

        draft = json.dumps({"summary": "草稿", "milestones": [], "conclusion": "完成"}, ensure_ascii=False)
        critic = json.dumps({"revised_roadmap": {
            "summary": "终稿", "milestones": [], "conclusion": "完成"
        }}, ensure_ascii=False)
        self.fake_model(draft, critic)
        response = self.client.post(
            "/api/agent/learning-path?target_role=前端工程师", headers=self.auth()
        )
        self.assertEqual(response.status_code, 502)
        with SessionLocal() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(DBRoadmap)), 0)

    def test_valid_stt_and_roadmap_flow_remain_available(self):
        from core.database import SessionLocal
        from models.db_models import DBRoadmap, DBUserProfile

        self.fake_model("<result>请介绍项目经历</result>")
        wav = self.wav_bytes()
        stt = self.client.post(
            "/api/audio/stt", headers=self.auth(),
            files={"file": ("x.wav", wav, "audio/wav")},
        )
        self.assertEqual(stt.status_code, 200, stt.text)
        self.assertEqual(stt.json()["text"], "请介绍项目经历")

        with SessionLocal() as db:
            if not db.scalar(select(DBUserProfile.id).where(DBUserProfile.user_id == 1)):
                db.add(DBUserProfile(user_id=1, major="计算机", current_skills="[]", certificates="[]"))
                db.commit()

        milestone = {
            "phase": "基础阶段", "period": "第 1-4 周",
            "focus_targets": ["完成一个项目"], "recommended_resources": ["官方文档"],
        }
        plan = {"summary": "学习计划", "milestones": [milestone], "conclusion": "按周复盘"}
        self.fake_model(
            json.dumps(plan, ensure_ascii=False),
            json.dumps({"revised_roadmap": plan}, ensure_ascii=False),
        )
        result = self.client.post(
            "/api/agent/learning-path?target_role=前端工程师", headers=self.auth()
        )
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["milestones"][0]["phase"], "基础阶段")
        with SessionLocal() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(DBRoadmap)), 1)
        self.assertEqual(self.client.get("/api/history/roadmaps", headers=self.auth(1)).json()["count"], 0)

    def test_z1_assessment_facts_override_extraction_and_keep_learning_time(self):
        self.fake_model(json.dumps({
            "name": "模型猜测", "current_skills": ["Java"], "soft_skills": ["模型猜测"],
            "interests": ["模型猜测"], "target_roles": ["测试工程师"]
        }, ensure_ascii=False))
        response = self.client.post("/api/user/profile/extract", headers=self.auth(), json={
            "resume_text": "用户填写的职业测评表单",
            "assessment": {
                "name": "真实用户", "major": "计算机", "current_skills": ["React"],
                "soft_skills": ["团队协作"], "interests": ["交互设计"],
                "target_roles": ["前端工程师"], "weekly_learning_time": "每周 6-10 小时",
            },
        })
        self.assertEqual(response.status_code, 200, response.text)
        profile = self.client.get("/api/profile/me", headers=self.auth()).json()
        self.assertEqual(profile["current_skills"], ["React"])
        self.assertEqual(profile["soft_skills"], ["团队协作"])
        self.assertEqual(profile["interests"], ["交互设计"])
        self.assertEqual(profile["weekly_learning_time"], "每周 6-10 小时")

    def test_z1_full_journey_uses_saved_user_data(self):
        """Exercise assessment -> profile -> match -> roadmap -> advisor as one journey."""
        self.seed_batch2_facts()
        plan = {"summary": "围绕 TypeScript 补齐前端能力", "milestones": [{
            "phase": "第一阶段", "period": "第 1 周", "focus_targets": ["完成 TypeScript 小项目"],
            "recommended_resources": ["TypeScript 官方文档"]
        }], "conclusion": "按进度复盘"}
        fake = self.fake_model(
            json.dumps({"name": "模型猜测", "current_skills": ["Java"]}, ensure_ascii=False),
            json.dumps(plan, ensure_ascii=False),
            json.dumps({"revised_roadmap": plan}, ensure_ascii=False),
            "先完成 TypeScript 小项目，再回看学习路径进度。",
        )
        assessment = self.client.post("/api/user/profile/extract", headers=self.auth(), json={
            "resume_text": "我希望成为前端工程师",
            "assessment": {
                "name": "链路验证用户", "major": "计算机", "current_skills": ["React"],
                "soft_skills": ["团队协作"], "interests": ["交互设计"],
                "target_roles": ["前端工程师"], "weekly_learning_time": "每周 6-10 小时",
            },
        })
        self.assertEqual(assessment.status_code, 200, assessment.text)
        profile = self.client.get("/api/profile/me", headers=self.auth()).json()
        self.assertEqual(profile["current_skills"], ["React"])
        matches = self.client.get("/api/recommendations", headers=self.auth()).json()["data"]
        match = next(item for item in matches if item["role_name"] == "前端开发工程师")
        self.assertEqual(match["score"], 47)
        self.assertIn("TypeScript", match["missing_skills"])

        roadmap = self.client.post("/api/agent/learning-path?target_role=前端工程师", headers=self.auth())
        self.assertEqual(roadmap.status_code, 200, roadmap.text)
        roadmap_id = roadmap.json()["id"]
        saved = self.client.get(f"/api/history/roadmaps/{roadmap_id}", headers=self.auth())
        self.assertEqual(saved.json()["summary"], plan["summary"])
        self.assertEqual(len(fake.calls), 3)
        self.assertEqual(self.client.get(f"/api/history/roadmaps/{roadmap_id}", headers=self.auth(1)).status_code, 404)

        created = self.client.post("/api/chat/sessions", headers=self.auth(), json={
            "target_role": "前端工程师", "roadmap_id": roadmap_id,
        })
        self.assertEqual(created.status_code, 200, created.text)
        session_id = created.json()["id"]
        chat = self.client.post("/api/agent/chat", headers=self.auth(), json={
            "session_id": session_id, "target_role": "前端工程师", "message": "下一步应该做什么？",
        })
        self.assertEqual(chat.status_code, 200, chat.text)
        context = fake.calls[3]["messages"][0]["content"]
        self.assertIn("每周 6-10 小时", context)
        self.assertIn("TypeScript", context)
        self.assertIn("完成 TypeScript 小项目", context)
        self.assertEqual(self.client.get(f"/api/chat/sessions/{session_id}", headers=self.auth(1)).status_code, 404)
        report = self.client.post(f"/api/report/export?roadmap_id={roadmap_id}", headers=self.auth())
        self.assertEqual(report.status_code, 200, report.text)
        self.assertIn(plan["summary"], report.text)
        self.assertEqual(len(fake.calls), 4)

    def test_z2_recommendations_and_gap_share_one_evidence_score(self):
        self.seed_batch2_facts()

        first = self.client.get("/api/recommendations", headers=self.auth()).json()["data"][0]
        second = self.client.get("/api/recommendations", headers=self.auth(1)).json()["data"][0]
        self.assertEqual(first["score"], 47)
        self.assertEqual(first["matched_skills"], ["React"])
        self.assertIn("TypeScript", first["missing_skills"])
        self.assertLess(second["score"], first["score"])

        dimension = {"score": 80, "analysis": "根据已填写能力解释", "suggestions": []}
        self.fake_model(json.dumps({
            "overall_match_score": 99, "basic": dimension, "skill": dimension,
            "soft": dimension, "potential": dimension,
            "immediate_next_steps": ["学习 TypeScript"], "roadmap_preview": "补齐核心技能"
        }, ensure_ascii=False))
        gap = self.client.post("/api/agent/gap-analysis?target_role=前端工程师", headers=self.auth())
        self.assertEqual(gap.status_code, 200, gap.text)
        self.assertEqual(gap.json()["overall_match_score"], first["score"])
        self.assertIn("TypeScript", gap.json()["missing_requirements"])

    def test_z2b_job_filter_accepts_matching_role_name_variants(self):
        conn = sqlite3.connect(self.main.DB_PATH)
        try:
            conn.execute("""CREATE TABLE IF NOT EXISTS jobs (
                title TEXT, location TEXT, salary_range TEXT, company TEXT, description TEXT)""")
            conn.execute("INSERT INTO jobs VALUES (?, ?, ?, ?, ?)",
                         ("前端开发工程师", "北京", "面议", "测试企业", "React 开发"))
            conn.commit()
        finally:
            conn.close()
        result = self.client.get("/api/jobs/search?keyword=前端工程师&limit=10")
        self.assertEqual(result.status_code, 200, result.text)
        self.assertTrue(any(item["title"] == "前端开发工程师" for item in result.json()["data"]))

    def test_z2c_missing_ability_evidence_has_no_invented_percentage(self):
        from core.database import SessionLocal
        from models.db_models import DBUserProfile
        self.seed_batch2_facts()
        with SessionLocal() as db:
            profile = db.query(DBUserProfile).filter(DBUserProfile.user_id == 1).one()
            profile.current_skills = "[]"
            profile.soft_skills = "[]"
            db.commit()
        matches = self.client.get("/api/recommendations", headers=self.auth()).json()["data"]
        self.assertIsNone(matches[0]["score"])
        gap = self.client.post("/api/agent/gap-analysis?target_role=前端工程师", headers=self.auth())
        self.assertEqual(gap.status_code, 422)

    def test_z3_saved_versions_progress_and_export_are_real_and_private(self):
        self.seed_batch2_facts()
        first_plan = {"summary": "第一版：先做组件", "milestones": [{
            "phase": "第一阶段", "period": "第 1 周", "focus_targets": ["完成 React 组件"],
            "recommended_resources": ["React 官方文档"]}], "conclusion": "复盘组件"}
        second_plan = {"summary": "第二版：补充类型", "milestones": [{
            "phase": "第二阶段", "period": "第 2 周", "focus_targets": ["完成 TypeScript 练习"],
            "recommended_resources": []}], "conclusion": "复盘类型"}
        fake = self.fake_model(*[
            json.dumps(value, ensure_ascii=False) for plan in (first_plan, second_plan)
            for value in (plan, {"revised_roadmap": plan})
        ])
        versions = []
        for _ in range(2):
            result = self.client.post("/api/agent/learning-path?target_role=前端工程师", headers=self.auth())
            self.assertEqual(result.status_code, 200, result.text)
            versions.append(result.json()["id"])
        self.assertNotEqual(*versions)
        self.assertEqual(len(fake.calls), 4)

        first = self.client.get(f"/api/history/roadmaps/{versions[0]}", headers=self.auth())
        self.assertEqual(first.json()["summary"], "第一版：先做组件")
        self.assertEqual(len(fake.calls), 4)
        self.assertEqual(self.client.get(f"/api/history/roadmaps/{versions[0]}", headers=self.auth(1)).status_code, 404)

        progress = self.client.put(f"/api/history/roadmaps/{versions[0]}/progress", headers=self.auth(),
                                   json={"completed_tasks": ["第一阶段::完成 React 组件"]})
        self.assertEqual(progress.status_code, 200, progress.text)
        self.assertEqual(self.client.put(f"/api/history/roadmaps/{versions[0]}/progress", headers=self.auth(1),
                                         json={"completed_tasks": []}).status_code, 404)
        report = self.client.post(f"/api/report/export?roadmap_id={versions[0]}&target_role=前端工程师",
                                  headers=self.auth())
        self.assertEqual(report.status_code, 200, report.text)
        self.assertIn("第一版：先做组件", report.text)
        self.assertIn("[x] 完成 React 组件", report.text)
        self.assertIn("每周 6-10 小时", report.text)
        self.assertNotIn("第二版：补充类型", report.text)
        self.assertNotIn("系统已为您生成了深度分析", report.text)
        self.assertEqual(len(fake.calls), 4)
        self.roadmap_id = versions[0]

    def test_z4_chat_sessions_use_bounded_private_context_and_clear(self):
        from core.database import SessionLocal
        from models.db_models import DBRoadmap

        self.seed_batch2_facts()
        snapshot = {"target_role": "前端工程师", "summary": "正在学习 React", "milestones": [{
            "phase": "第一阶段", "period": "第 1 周", "focus_targets": ["完成 React 组件"],
            "recommended_resources": ["React 官方文档"]}], "conclusion": "继续练习"}
        with SessionLocal() as db:
            record = DBRoadmap(user_id=1, role_name="前端工程师",
                               roadmap_json=json.dumps(snapshot, ensure_ascii=False),
                               progress_json='["第一阶段::完成 React 组件"]')
            db.add(record)
            db.commit()
            db.refresh(record)
            roadmap_id = record.id
        created = self.client.post("/api/chat/sessions", headers=self.auth(), json={
            "target_role": "前端工程师", "roadmap_id": roadmap_id,
        })
        self.assertEqual(created.status_code, 200, created.text)
        session_id = created.json()["id"]
        self.assertEqual(self.client.get(f"/api/chat/sessions/{session_id}", headers=self.auth(1)).status_code, 404)

        from models.db_models import DBChatMessage
        with SessionLocal() as db:
            for number in range(12):
                db.add(DBChatMessage(user_id=1, session_id=session_id, role="user", content=f"历史问题 {number}"))
            db.add(DBChatMessage(user_id=2, session_id=session_id, role="user", content="第二位用户的私有消息"))
            db.commit()

        fake = self.fake_model('第一条真实回答 [[GRAPH_START]]{"type":"career_map","levels":[]}[[GRAPH_END]]', "新对话回答")
        sent = self.client.post("/api/agent/chat", headers=self.auth(), json={
            "session_id": session_id, "target_role": "前端工程师", "message": "请根据当前进度建议下一步"
        })
        self.assertEqual(sent.status_code, 200, sent.text)
        context = fake.calls[0]["messages"][0]["content"]
        self.assertIn("每周 6-10 小时", context)
        self.assertIn("完成 React 组件", context)
        self.assertIn("TypeScript", context)
        self.assertLess(len(context), 8000)
        self.assertLessEqual(len(fake.calls[0]["messages"]), 10)
        self.assertNotIn("第二位用户的私有消息", str(fake.calls[0]["messages"]))
        saved = self.client.get(f"/api/chat/sessions/{session_id}", headers=self.auth()).json()
        self.assertEqual(saved["messages"][-1]["graph_data"]["type"], "career_map")

        from models.db_models import DBUserProfile
        with SessionLocal() as db:
            profile = db.query(DBUserProfile).filter(DBUserProfile.user_id == 1).one()
            long_values = json.dumps(["很长的已填资料" * 30 for _ in range(20)], ensure_ascii=False)
            profile.interests = long_values
            profile.certificates = long_values
            profile.current_skills = long_values
            profile.soft_skills = long_values
            profile.target_roles = long_values
            db.commit()
            bounded = self.main.advisor_context(db, 1, "前端工程师", roadmap_id)
        self.assertLessEqual(len(bounded), 4500)
        self.assertEqual(json.loads(bounded)["current_roadmap"]["id"], roadmap_id)

        changed_role = self.client.post("/api/agent/chat", headers=self.auth(), json={
            "session_id": session_id, "target_role": "后端工程师", "message": "换个方向"
        })
        self.assertEqual(changed_role.status_code, 409)
        self.assertEqual(len(fake.calls), 1)

        cleared = self.client.delete(f"/api/chat/sessions/{session_id}", headers=self.auth())
        self.assertEqual(cleared.status_code, 200, cleared.text)
        self.assertEqual(self.client.get(f"/api/chat/sessions/{session_id}", headers=self.auth()).status_code, 404)
        old = self.client.post("/api/agent/chat", headers=self.auth(), json={
            "session_id": session_id, "message": "继续旧对话"
        })
        self.assertEqual(old.status_code, 409)

        new_session = self.client.post("/api/chat/sessions", headers=self.auth(), json={"target_role": "前端工程师"}).json()["id"]
        fresh = self.client.post("/api/agent/chat", headers=self.auth(), json={
            "session_id": new_session, "message": "一个新问题"
        })
        self.assertEqual(fresh.status_code, 200, fresh.text)
        self.assertEqual(len(fake.calls[1]["messages"]), 2)

    def test_z5_retry_keys_return_saved_records_without_new_model_calls(self):
        from core.database import SessionLocal
        from models.db_models import DBInterview, DBRoadmap
        self.seed_batch2_facts()
        plan = {"summary": "按周完成项目", "milestones": [{"phase": "第一阶段", "period": "第 1 周",
                 "focus_targets": ["完成组件"], "recommended_resources": []}], "conclusion": "复盘"}
        fake = self.fake_model(json.dumps(plan, ensure_ascii=False),
                               json.dumps({"revised_roadmap": plan}, ensure_ascii=False))
        key = str(uuid.uuid4())
        url = "/api/agent/learning-path?target_role=前端工程师"
        headers = {**self.auth(), "Idempotency-Key": key}
        first = self.client.post(url, headers=headers)
        repeated = self.client.post(url, headers=headers)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(repeated.json()["id"], first.json()["id"])
        self.assertEqual(len(fake.calls), 2)
        self.assertEqual(self.client.post("/api/agent/learning-path?target_role=产品经理",
                                          headers=headers).status_code, 409)
        with SessionLocal() as db:
            self.assertEqual(db.query(DBRoadmap).filter(DBRoadmap.request_key == key).count(), 1)

        evaluation = {"score": 76, "evaluation": "有依据", "improvement_suggestion": "补充实例",
                      "reference_answer": "解释实现和结果"}
        fake = self.fake_model(json.dumps(evaluation, ensure_ascii=False))
        key = str(uuid.uuid4())
        headers = {**self.auth(), "Idempotency-Key": key}
        payload = {"target_role": "前端工程师", "question": "如何设计组件？",
                   "user_answer": "先拆职责", "focus_area": "组件设计"}
        first = self.client.post("/api/agent/mock-interview/evaluate", headers=headers, json=payload)
        repeated = self.client.post("/api/agent/mock-interview/evaluate", headers=headers, json=payload)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(repeated.json(), first.json())
        self.assertEqual(len(fake.calls), 1)
        self.assertEqual(self.client.post("/api/agent/mock-interview/evaluate", headers=headers,
                                          json={**payload, "focus_area": "性能"}).status_code, 409)
        with SessionLocal() as db:
            self.assertEqual(db.query(DBInterview).filter(DBInterview.request_key == key).count(), 1)

    def test_z6_audio_status_covers_pending_success_failure_and_ownership(self):
        from core.database import SessionLocal
        from models.db_models import DBAudioJob
        audio_dir = Path(self.temp.name) / "audio-jobs"
        audio_dir.mkdir(exist_ok=True)
        old_audio_dir = self.main.AUDIO_DIR
        self.main.AUDIO_DIR = str(audio_dir)
        try:
            filename = f"gen_q_{uuid.uuid4()}.wav"
            now = self.main.datetime.now(self.main.timezone.utc).isoformat()
            with SessionLocal() as db:
                db.add(DBAudioJob(filename=filename, user_id=1, status="pending",
                                  created_at=now, updated_at=now))
                db.commit()
            status_url = f"/api/audio/status/{filename}"
            self.assertEqual(self.client.get(status_url, headers=self.auth()).json()["status"], "pending")
            self.assertEqual(self.client.get(status_url, headers=self.auth(1)).status_code, 404)
            audio_url = self.main.signed_audio_url(filename, 1)
            self.assertEqual(self.client.get(audio_url).status_code, 425)
            self.main.client = SimpleNamespace(audio=SimpleNamespace(speech=lambda **kwargs:
                SimpleNamespace(stream_to_file=lambda path: Path(path).write_bytes(self.wav_bytes()))))
            self.main.task_generate_tts("题目", str(audio_dir / filename))
            self.assertEqual(self.client.get(status_url, headers=self.auth()).json()["status"], "success")
            self.assertEqual(self.client.get(audio_url).status_code, 200)

            failed_name = f"gen_q_{uuid.uuid4()}.wav"
            with SessionLocal() as db:
                db.add(DBAudioJob(filename=failed_name, user_id=1, status="pending",
                                  created_at=now, updated_at=now))
                db.commit()
            def fail_speech(**kwargs):
                raise RuntimeError("provider unavailable")
            self.main.client = SimpleNamespace(audio=SimpleNamespace(speech=fail_speech))
            self.main.task_generate_tts("题目", str(audio_dir / failed_name))
            self.assertEqual(self.client.get(f"/api/audio/status/{failed_name}",
                                             headers=self.auth()).json()["status"], "failed")
            self.assertEqual(self.client.get(self.main.signed_audio_url(failed_name, 1)).status_code, 410)
        finally:
            self.main.AUDIO_DIR = old_audio_dir

    def test_z7_ai_timeout_is_classified_and_history_queries_are_bounded(self):
        import httpx
        from zhipuai import APITimeoutError
        def timeout(**kwargs):
            raise APITimeoutError(request=httpx.Request("POST", "https://example.invalid"))
        self.main.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=timeout)))
        result = self.client.post("/api/agent/chat", headers=self.auth(), json={"message": "测试超时"})
        self.assertEqual(result.status_code, 504, result.text)
        self.assertEqual(self.client.get("/api/history/roadmaps?limit=101", headers=self.auth()).status_code, 422)
        self.assertEqual(self.client.get("/api/history/interviews?limit=101", headers=self.auth()).status_code, 422)

        models = []
        def fail_then_fallback(**kwargs):
            models.append(kwargs["model"])
            if len(models) == 1:
                raise APITimeoutError(request=httpx.Request("POST", "https://example.invalid"))
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="备用模型回答"))])
        old_fallback = self.main.AI_FALLBACK_MODEL
        self.main.AI_FALLBACK_MODEL = "backup-text-model"
        self.main.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=fail_then_fallback)))
        try:
            response = self.main.ai_completion_sync(model="primary-text-model", messages=[])
            self.assertEqual(response.choices[0].message.content, "备用模型回答")
            self.assertEqual(models, ["primary-text-model", "backup-text-model"])
        finally:
            self.main.AI_FALLBACK_MODEL = old_fallback

    def test_z8_targeted_interview_uses_local_bounded_weakness_summary(self):
        from core.database import SessionLocal
        from models.db_models import DBInterview
        self.seed_batch2_facts()
        with SessionLocal() as db:
            for number in range(6):
                db.add(DBInterview(user_id=1, target_role="前端工程师", question=f"题目 {number}",
                    user_answer="回答", score=50, evaluation="待改进",
                    improvement_suggestion=f"弱点 {number}: 补充案例", reference_answer="示例"))
            db.commit()
        fake = self.fake_model(json.dumps({"role": "前端工程师", "difficulty": "初级",
            "question": "如何设计组件？", "focus_topic": "组件设计", "background_context": "历史弱点"}, ensure_ascii=False))
        result = self.client.get("/api/interview/generate-targeted?target_role=前端工程师",
                                 headers=self.auth())
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(len(fake.calls), 1)
        self.assertIn("弱点 5", fake.calls[0]["messages"][1]["content"])
        self.assertLess(len(fake.calls[0]["messages"][1]["content"]), 5000)

    def test_z9_chat_retry_returns_saved_reply_without_duplicate_messages(self):
        from core.database import SessionLocal
        from models.db_models import DBChatMessage
        session_id = self.client.post("/api/chat/sessions", headers=self.auth(),
                                      json={"target_role": "前端工程师"}).json()["id"]
        request_id = str(uuid.uuid4())
        payload = {"session_id": session_id, "request_id": request_id,
                   "target_role": "前端工程师", "message": "请给我建议"}
        fake = self.fake_model("请先完成一个组件项目")
        first = self.client.post("/api/agent/chat", headers=self.auth(), json=payload)
        second = self.client.post("/api/agent/chat", headers=self.auth(), json=payload)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.json(), first.json())
        self.assertEqual(len(fake.calls), 1)
        self.assertEqual(self.client.post("/api/agent/chat", headers=self.auth(),
                                          json={**payload, "message": "换一个问题"}).status_code, 409)
        with SessionLocal() as db:
            self.assertEqual(db.query(DBChatMessage).filter(DBChatMessage.user_id == 1,
                DBChatMessage.session_id == session_id, DBChatMessage.request_key == request_id).count(), 2)


if __name__ == "__main__":
    unittest.main()
