"""Business boundaries for the six sourced pilot roles, not model accuracy."""

import unittest
from types import SimpleNamespace

from core.matching import score_role
from core.standards import load_pilot_dataset


class PilotMatchingTests(unittest.TestCase):
    def test_each_full_role_profile_covers_its_standard(self):
        for role in load_pilot_dataset().roles:
            with self.subTest(role=role.role_name):
                standard = SimpleNamespace(**role.model_dump())
                result = score_role({"current_skills": role.core_skills,
                                     "soft_skills": role.soft_skills,
                                     "target_roles": [role.role_name]}, standard)
                self.assertEqual(result["score"], 100)
                self.assertEqual(result["missing_skills"], [])

    def test_explicit_aliases_match_but_generic_software_does_not(self):
        role = next(r for r in load_pilot_dataset().roles if r.role_name == "招聘助理")
        standard = SimpleNamespace(**role.model_dump())
        result = score_role({"current_skills": ["Microsoft Excel", "简历初筛", "面试安排"]}, standard)
        self.assertCountEqual(result["matched_skills"], ["电子表格", "简历筛选", "面试协调"])
        vague = score_role({"current_skills": ["Office", "HR", "数据分析"]}, standard)
        self.assertEqual(vague["matched_skills"], [])

    def test_empty_pilot_profile_has_no_invented_score(self):
        for role in load_pilot_dataset().roles:
            result = score_role({"target_roles": [role.role_name]}, SimpleNamespace(**role.model_dump()))
            self.assertIsNone(result["score"])
            self.assertEqual(result["matched_skills"], [])

    def test_content_skills_do_not_establish_recruiting_tasks(self):
        role = next(r for r in load_pilot_dataset().roles if r.role_name == "招聘助理")
        result = score_role({"current_skills": ["内容策划", "图文编辑", "平台运营"]},
                            SimpleNamespace(**role.model_dump()))
        self.assertEqual(result["matched_skills"], [])


if __name__ == "__main__":
    unittest.main()
