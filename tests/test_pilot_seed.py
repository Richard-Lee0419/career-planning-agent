"""Data-integrity checks for import provenance, collisions and review validity."""

import copy
import json
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from core.database import Base
from core.standards import load_pilot_dataset, standard_metadata
from models.db_models import DBJobStandardMetadata, DBJobStandardProfile
from scripts.seed_pilot_standards import seed_pilot_standards


class PilotSeedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "pilot.json"
        self.engine = create_engine(f"sqlite:///{Path(self.temp.name) / 'pilot.db'}")
        Base.metadata.create_all(bind=self.engine)
        self.db = Session(self.engine, autoflush=False)
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)

    @staticmethod
    def package():
        # These are synthetic integrity fixtures, not published job standards.
        return {
            "schema_version": "1.0", "version": "fixture-1",
            "domains": [{"id": "example", "label": "合成测试领域"}],
            "roles": [{
                "role_id": "fixture-assistant", "role_name": "合成测试助理",
                "domain": "example", "domain_label": "合成测试领域",
                "description": "仅用于验证来源数据完整性", "core_skills": ["测试能力"],
                "soft_skills": ["测试协作"], "certifications": [],
                "standard_source": {
                    "type": "manual_pilot", "version": "fixture-1", "region": "中国大陆",
                    "review_status": "source_checked", "reviewed_at": "2026-10-11",
                    "sources": [{"title": "合成链接", "url": "https://example.org/fixture",
                                 "kind": "education_standard", "published_at": "2025",
                                 "evidence_location": "第 1 页测试位置", "accessed_at": "2026-10-11",
                                 "access_status": "正文已核对"}],
                    "limitations": ["合成测试数据，无真实职业含义"], "tasks": ["验证导入"],
                },
            }],
        }

    def write_package(self, data=None):
        self.path.write_text(json.dumps(data or self.package(), ensure_ascii=False), encoding="utf-8")
        return self.path

    def test_import_is_idempotent_and_keeps_linked_source_record(self):
        path = self.write_package()
        self.assertEqual(seed_pilot_standards(self.db, path), 1)
        standard = self.db.query(DBJobStandardProfile).one()
        metadata_before = self.db.get(DBJobStandardMetadata, standard.id).metadata_json
        self.assertEqual(seed_pilot_standards(self.db, path), 0)
        self.assertEqual(self.db.query(DBJobStandardProfile).count(), 1)
        self.assertEqual(self.db.query(DBJobStandardMetadata).count(), 1)
        self.assertEqual(self.db.get(DBJobStandardMetadata, standard.id).metadata_json, metadata_before)
        info = standard_metadata(self.db, standard)
        self.assertEqual(info["role_id"], "fixture-assistant")
        self.assertEqual(info["standard_source"]["review_status"], "source_checked")
        self.assertEqual(info["standard_source"]["sources"][0]["published_at"], "2025")
        self.assertEqual(info["standard_source"]["sources"][0]["evidence_location"], "第 1 页测试位置")
        self.assertEqual(info["standard_source"]["sources"][0]["accessed_at"], "2026-10-11")

    def test_name_collision_does_not_overwrite_or_certify_old_standard(self):
        old = DBJobStandardProfile(role_name="合成测试助理", description="旧未审核内容",
            core_skills='["原能力"]', soft_skills="[]", certifications="[]")
        self.db.add(old)
        self.db.commit()
        self.assertEqual(seed_pilot_standards(self.db, self.write_package()), 0)
        self.db.refresh(old)
        self.assertEqual(old.description, "旧未审核内容")
        self.assertEqual(json.loads(old.core_skills), ["原能力"])
        self.assertEqual(self.db.query(DBJobStandardMetadata).count(), 0)
        self.assertEqual(standard_metadata(self.db, old)["standard_source"]["type"], "legacy_unverified")

    def test_modified_standard_loses_current_review_without_erasing_original_sources(self):
        path = self.write_package()
        seed_pilot_standards(self.db, path)
        standard = self.db.query(DBJobStandardProfile).one()
        original_sources = standard_metadata(self.db, standard)["standard_source"]["sources"]
        for field, changed in (("core_skills", '["改动能力"]'), ("description", "已改动说明")):
            with self.subTest(field=field):
                previous = getattr(standard, field)
                setattr(standard, field, changed)
                self.db.commit()
                self.assertEqual(seed_pilot_standards(self.db, path), 0)
                info = standard_metadata(self.db, standard)
                self.assertEqual(info["standard_source"]["review_status"], "modified_unverified")
                self.assertEqual(info["standard_source"]["sources"], original_sources)
                self.assertEqual(json.loads(self.db.get(DBJobStandardMetadata, standard.id).metadata_json)
                                 ["standard_source"]["review_status"], "source_checked")
                setattr(standard, field, previous)
                self.db.commit()
                self.assertEqual(standard_metadata(self.db, standard)["standard_source"]["review_status"],
                                 "source_checked")

    def test_invalid_second_role_leaves_no_partial_import(self):
        data = self.package()
        second = copy.deepcopy(data["roles"][0])
        second.update(role_id="second", role_name="第二个合成岗位", core_skills=[])
        data["roles"].append(second)
        with self.assertRaises(ValidationError):
            seed_pilot_standards(self.db, self.write_package(data))
        self.assertEqual(self.db.query(DBJobStandardProfile).count(), 0)
        self.assertEqual(self.db.query(DBJobStandardMetadata).count(), 0)

    def test_invalid_sources_and_catalog_relations_are_rejected(self):
        examples = []
        for changes in (
            {"sources": []}, {"sources": [{"title": "无效链接", "url": "file:///private/source",
                                         "kind": "education_standard"}]},
            {"tasks": [" "]}, {"limitations": []}, {"reviewed_at": "not-a-date"},
            {"published_at": None},
        ):
            data = self.package()
            if "published_at" in changes:
                # Unknown publication dates are legitimate and must remain null.
                data["roles"][0]["standard_source"]["sources"][0]["published_at"] = None
                loaded = load_pilot_dataset(self.write_package(data))
                self.assertIsNone(loaded.roles[0].standard_source.sources[0].published_at)
                continue
            data["roles"][0]["standard_source"].update(changes)
            examples.append(data)
        for field, value in (("domain", "absent"), ("domain_label", "错误标签")):
            data = self.package()
            data["roles"][0][field] = value
            examples.append(data)
        duplicate = self.package()
        duplicate["roles"].append(copy.deepcopy(duplicate["roles"][0]))
        examples.append(duplicate)
        for data in examples:
            with self.subTest(data=data):
                with self.assertRaises(ValidationError):
                    seed_pilot_standards(self.db, self.write_package(data))
        self.assertEqual(self.db.query(DBJobStandardProfile).count(), 0)

    def test_unmanaged_demo_and_unknown_role_have_honest_classification(self):
        demo = DBJobStandardProfile(role_name="前端开发工程师", description="演示用岗位标准：用于本地运行",
                                   core_skills='["React"]', soft_skills="[]", certifications="[]")
        unknown = DBJobStandardProfile(role_name="未知领域助理", description="无来源的岗位",
                                      core_skills="[]", soft_skills="[]", certifications="[]")
        self.db.add_all([demo, unknown])
        self.db.commit()
        demo_info = standard_metadata(self.db, demo)
        self.assertEqual(demo_info["domain"], "technology")
        self.assertEqual(demo_info["standard_source"]["type"], "demo_example")
        self.assertEqual(demo_info["standard_source"]["sources"], [])
        unknown_info = standard_metadata(self.db, unknown)
        self.assertEqual(unknown_info["domain"], "unclassified")
        self.assertEqual(unknown_info["standard_source"]["review_status"], "unverified")

    def test_skill_mapping_requires_known_ids_and_unambiguous_aliases(self):
        data = self.package()
        data["skill_ids"] = {"测试能力": "skill-test", "测试协作": "skill-team"}
        data["skill_aliases"] = {"测试能力": ["测试别名"]}
        loaded = load_pilot_dataset(self.write_package(data))
        self.assertEqual(loaded.skill_aliases["测试能力"], ["测试别名"])
        self.assertEqual(loaded.skill_ids["测试能力"], "skill-test")
        invalid = []
        duplicate_ids = copy.deepcopy(data)
        duplicate_ids["skill_ids"]["测试协作"] = "skill-test"
        invalid.append(duplicate_ids)
        unknown = copy.deepcopy(data)
        unknown["skill_ids"]["不存在的能力"] = "skill-absent"
        invalid.append(unknown)
        no_id = copy.deepcopy(data)
        no_id["skill_aliases"]["没有 ID 的能力"] = ["别名"]
        invalid.append(no_id)
        ambiguous = copy.deepcopy(data)
        ambiguous["skill_aliases"] = {"测试能力": ["Same Alias"], "测试协作": ["ｓａｍｅ ａｌｉａｓ"]}
        invalid.append(ambiguous)
        canonical_collision = copy.deepcopy(data)
        canonical_collision["skill_aliases"] = {"测试能力": ["测试协作"]}
        invalid.append(canonical_collision)
        for package in invalid:
            with self.subTest(package=package):
                with self.assertRaises(ValidationError):
                    seed_pilot_standards(self.db, self.write_package(package))
        self.assertEqual(self.db.query(DBJobStandardProfile).count(), 0)

    def test_corrupt_metadata_cannot_retain_reviewed_status(self):
        seed_pilot_standards(self.db, self.write_package())
        standard = self.db.query(DBJobStandardProfile).one()
        row = self.db.get(DBJobStandardMetadata, standard.id)
        row.metadata_json = '{"standard_source":{"review_status":"source_checked"}}'
        self.db.commit()
        info = standard_metadata(self.db, standard)
        self.assertEqual(info["standard_source"]["review_status"], "unverified")
        self.assertTrue(any("格式无效" in text for text in info["standard_source"]["limitations"]))


if __name__ == "__main__":
    unittest.main()
