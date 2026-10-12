"""HTTP regressions for saved context and untrusted structured AI responses.

The database and PDF are real; only the external model client is replaced.
"""

import importlib
import json
import os
import secrets
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import test_batch1 as fixtures


class ReliabilityRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from core import database
        from models.db_models import Base

        cls.temp = tempfile.TemporaryDirectory()
        os.environ["JWT_SECRET_KEY"] = secrets.token_urlsafe(48)
        os.environ["ZHIPUAI_API_KEY"] = "isolated-test-key"
        cls.original_database = (database.engine, database.SessionLocal, database.DB_PATH)
        database.DB_PATH = str(Path(cls.temp.name) / "reliability.db")
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
        response = cls.client.post(
            "/api/auth/register", json={"username": "reliability_user", "password": "TestPass123!"}
        )
        assert response.status_code == 200, response.text
        login = cls.client.post(
            "/api/auth/login", data={"username": "reliability_user", "password": "TestPass123!"}
        )
        assert login.status_code == 200, login.text
        cls.tokens = [login.json()["access_token"]]

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
        from models.db_models import DBChatMessage, DBChatSession, DBRoadmap, DBUserProfile

        # Each isolated test user has ID 1. Do not share the previous suite's
        # per-user rate-limit bucket with this different database/user.
        previous_attempts = self.main._ai_attempts.pop(1, None)

        def restore_limit_bucket():
            self.main._ai_attempts.pop(1, None)
            if previous_attempts is not None:
                self.main._ai_attempts[1] = previous_attempts

        self.addCleanup(restore_limit_bucket)
        with SessionLocal() as db:
            for model in (DBChatMessage, DBChatSession, DBRoadmap, DBUserProfile):
                db.query(model).delete()
            db.commit()

    def seed_roadmap(self, summary):
        from core.database import SessionLocal
        from models.db_models import DBRoadmap

        with SessionLocal() as db:
            record = DBRoadmap(user_id=1, role_name="前端工程师", roadmap_json=json.dumps({
                "summary": summary, "milestones": [], "conclusion": "继续学习"
            }, ensure_ascii=False))
            db.add(record)
            db.commit()
            return record.id

    def test_existing_session_keeps_changed_roadmap_after_save_and_continuation(self):
        old_id = self.seed_roadmap("旧路径独有：先复习布局")
        new_id = self.seed_roadmap("新路径独有：完成类型练习")
        session_id = self.client.post("/api/chat/sessions", headers=self.auth(), json={
            "target_role": "前端工程师", "roadmap_id": old_id
        }).json()["id"]
        fake = self.fake_model("参考新路径", "继续新路径")
        changed = self.client.post("/api/agent/chat", headers=self.auth(), json={
            "session_id": session_id, "roadmap_id": new_id, "message": "用新版本给我建议"
        })
        self.assertEqual(changed.status_code, 200, changed.text)
        saved = self.client.get(f"/api/chat/sessions/{session_id}", headers=self.auth())
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json()["roadmap_id"], new_id)
        continued = self.client.post("/api/agent/chat", headers=self.auth(), json={
            "session_id": session_id, "message": "继续建议"
        })
        self.assertEqual(continued.status_code, 200, continued.text)
        for call in fake.calls:
            context = call["messages"][0]["content"]
            self.assertIn("新路径独有", context)
            self.assertNotIn("旧路径独有", context)

    def test_empty_saved_session_keeps_first_target_and_roadmap(self):
        roadmap_id = self.seed_roadmap("首次绑定路径")
        session_id = self.client.post(
            "/api/chat/sessions", headers=self.auth(), json={}
        ).json()["id"]
        self.fake_model("按首次路径开始")
        response = self.client.post("/api/agent/chat", headers=self.auth(), json={
            "session_id": session_id, "target_role": "前端工程师", "roadmap_id": roadmap_id,
            "message": "给我学习建议"
        })
        self.assertEqual(response.status_code, 200, response.text)
        saved = self.client.get(f"/api/chat/sessions/{session_id}", headers=self.auth()).json()
        self.assertEqual(saved["target_role"], "前端工程师")
        self.assertEqual(saved["roadmap_id"], roadmap_id)

    def test_session_cleared_during_model_call_rejects_late_reply_without_write_lock(self):
        from core.database import SessionLocal
        from models.db_models import DBChatMessage, DBChatSession

        roadmap_id = self.seed_roadmap("正在切换的路径")
        session_id = self.client.post(
            "/api/chat/sessions", headers=self.auth(), json={}
        ).json()["id"]

        def complete_after_clear(**kwargs):
            cleared = self.client.delete(f"/api/chat/sessions/{session_id}", headers=self.auth())
            self.assertEqual(cleared.status_code, 200, cleared.text)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="晚到的回答"))])

        self.main.client = SimpleNamespace(chat=SimpleNamespace(
            completions=SimpleNamespace(create=complete_after_clear)
        ))
        response = self.client.post("/api/agent/chat", headers=self.auth(), json={
            "session_id": session_id, "target_role": "前端工程师", "roadmap_id": roadmap_id,
            "message": "生成建议期间清空"
        })
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(self.client.get(f"/api/chat/sessions/{session_id}", headers=self.auth()).status_code, 404)
        with SessionLocal() as db:
            self.assertEqual(db.query(DBChatMessage).filter(DBChatMessage.session_id == session_id).count(), 0)
            record = db.query(DBChatSession).filter(DBChatSession.id == session_id).one()
            self.assertIsNotNone(record.closed_at)
            self.assertIsNone(record.roadmap_id)
            self.assertIsNone(record.target_role)

    @staticmethod
    def resume_pdf():
        """Build a tiny valid text PDF without a new runtime dependency."""
        text = b"BT /F1 12 Tf 40 760 Td (Student resume: Java and teamwork.) Tj ET"
        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            b"<< /Length " + str(len(text)).encode() + b" >>\nstream\n" + text + b"\nendstream",
        ]
        document = b"%PDF-1.4\n"
        offsets = [0]
        for number, body in enumerate(objects, 1):
            offsets.append(len(document))
            document += str(number).encode() + b" 0 obj\n" + body + b"\nendobj\n"
        xref = len(document)
        document += b"xref\n0 6\n0000000000 65535 f \n"
        document += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
        document += b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n" + str(xref).encode() + b"\n%%EOF"
        return document

    @staticmethod
    def valid_extracted_profile():
        return {
            "name": "学生", "education_level": "本科", "major": "软件工程",
            "current_skills": ["Java"], "certificates": [], "internship_experience": None,
            "target_roles": ["后端工程师"], "soft_skills": ["团队协作"]
        }

    def test_invalid_pdf_extraction_does_not_overwrite_existing_profile(self):
        from core.database import SessionLocal
        from models.db_models import DBUserProfile

        with SessionLocal() as db:
            db.add(DBUserProfile(user_id=1, major="原专业", current_skills='["React"]',
                                 soft_skills="[]", target_roles="[]", certificates="[]"))
            db.commit()
        invalid_outputs = [
            {}, [],
            {**self.valid_extracted_profile(), "current_skills": [{"name": "Java"}]},
            {**self.valid_extracted_profile(), "certificates": "暂无"},
            {**self.valid_extracted_profile(), "internship_experience": {"company": "某企业"}},
        ]
        for output in invalid_outputs:
            with self.subTest(output=output):
                self.fake_model(json.dumps(output, ensure_ascii=False))
                response = self.client.post("/api/user/profile/upload-resume", headers=self.auth(),
                    files={"file": ("resume.pdf", self.resume_pdf(), "application/pdf")})
                self.assertEqual(response.status_code, 502, response.text)
                with SessionLocal() as db:
                    profile = db.query(DBUserProfile).filter(DBUserProfile.user_id == 1).one()
                    self.assertEqual(profile.major, "原专业")
                    self.assertEqual(json.loads(profile.current_skills), ["React"])

    def test_valid_pdf_extraction_remains_persisted_and_readable(self):
        fake = self.fake_model(json.dumps(self.valid_extracted_profile(), ensure_ascii=False))
        response = self.client.post("/api/user/profile/upload-resume", headers=self.auth(),
            files={"file": ("resume.pdf", self.resume_pdf(), "application/pdf")})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("Student resume", fake.calls[0]["messages"][1]["content"])
        saved = self.client.get("/api/profile/me", headers=self.auth())
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json()["current_skills"], ["Java"])
        self.assertEqual(saved.json()["soft_skills"], ["团队协作"])

    def test_invalid_interview_graph_is_rejected_without_saving_messages(self):
        from core.database import SessionLocal
        from models.db_models import DBChatMessage

        invalid_outputs = [
            {"type": "mock_interview", "role": "前端工程师", "questions": {}},
            {"type": "mock_interview", "role": "前端工程师", "questions": []},
            {"type": "mock_interview", "role": "前端工程师", "questions": [" "]},
            {"type": "mock_interview", "role": "前端工程师", "questions": [23]},
            {"type": "mock_interview", "questions": ["请介绍项目"]},
        ]
        for output in invalid_outputs:
            with self.subTest(output=output):
                self.fake_model("开始面试 [[GRAPH_START]]" + json.dumps(output, ensure_ascii=False) + "[[GRAPH_END]]")
                response = self.client.post("/api/agent/chat", headers=self.auth(), json={
                    "message": "给我模拟面试题组"
                })
                self.assertEqual(response.status_code, 502, response.text)
                with SessionLocal() as db:
                    self.assertEqual(db.query(DBChatMessage).count(), 0)

    def test_valid_interview_graph_has_nonempty_reply_and_saved_questions(self):
        graph = {"type": "mock_interview", "role": " 前端工程师 ", "questions": [" 请介绍项目 "]}
        self.fake_model("[[GRAPH_START]]" + json.dumps(graph, ensure_ascii=False) + "[[GRAPH_END]]")
        response = self.client.post("/api/agent/chat", headers=self.auth(), json={"message": "开始模拟面试"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["reply"].strip())
        session_id = response.json()["session_id"]
        saved = self.client.get(f"/api/chat/sessions/{session_id}", headers=self.auth()).json()
        self.assertEqual(saved["messages"][-1]["graph_data"]["questions"], ["请介绍项目"])
        self.assertEqual(saved["messages"][-1]["graph_data"]["role"], "前端工程师")


if __name__ == "__main__":
    unittest.main()
