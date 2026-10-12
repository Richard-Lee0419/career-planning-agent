"""Matching outcomes for complete, ambiguous and missing self-reported abilities.

These tests use public demo standards and in-memory profiles, without a database
or AI service. They protect scores and gaps visible to a project user.
"""

import json
import unittest
from pathlib import Path
from types import SimpleNamespace

from core.matching import role_matches, score_role


class MatchingRegressionTests(unittest.TestCase):
    @staticmethod
    def standard(skills, soft=None, name="测试岗位", description=""):
        return SimpleNamespace(
            role_name=name, core_skills=skills, soft_skills=soft or [],
            description=description,
        )

    def test_complete_public_demo_profiles_have_no_false_gaps(self):
        standards = json.loads(
            (Path(__file__).resolve().parents[1] / "data" / "demo_job_standards.json").read_text(encoding="utf-8")
        )
        for data in standards:
            with self.subTest(role=data["role_name"]):
                result = score_role({
                    "current_skills": data["core_skills"],
                    "soft_skills": data["soft_skills"],
                    "target_roles": [data["role_name"]],
                }, SimpleNamespace(**data))
                self.assertEqual(result["score"], 100)
                self.assertEqual(result["missing_skills"], [])
                self.assertEqual(result["missing_soft_skills"], [])

    def test_case_whitespace_and_fullwidth_spelling_match_symmetrically(self):
        result = score_role({"current_skills": [" SpringBoot ", "rest api", "ＨＴＭＬ／ＣＳＳ", "ｃ＋＋"]},
                            self.standard(["spring boot", "REST API", "HTML/CSS", "C++"]))
        self.assertEqual(result["matched_skills"], ["spring boot", "REST API", "HTML/CSS", "C++"])
        self.assertEqual(result["missing_skills"], [])

    def test_c_family_languages_are_distinct_and_single_c_is_valid(self):
        for reported in ("C", "C++", "C#"):
            with self.subTest(reported=reported):
                result = score_role({"current_skills": [reported]}, self.standard(["C", "C++", "C#"]))
                self.assertEqual(result["matched_skills"], [reported])
                self.assertEqual(set(result["missing_skills"]), {"C", "C++", "C#"} - {reported})

    def test_java_and_javascript_are_not_interchangeable(self):
        for reported, expected in (("Java", "Java"), ("JavaScript", "JavaScript"), ("JS", "JavaScript")):
            with self.subTest(reported=reported):
                result = score_role({"current_skills": [reported]}, self.standard(["Java", "JavaScript"]))
                self.assertEqual(result["matched_skills"], [expected])
                self.assertEqual(len(result["missing_skills"]), 1)

    def test_small_explicit_aliases_work_without_reinterpreting_other_skills(self):
        result = score_role({"current_skills": ["TS", "spring-boot", "RESTful API"],
                             "soft_skills": ["团队合作", "沟通协调"]},
                            self.standard(["TypeScript", "Spring Boot", "REST API", "Java"], ["团队协作", "沟通"]))
        self.assertEqual(result["matched_skills"], ["TypeScript", "Spring Boot", "REST API"])
        self.assertEqual(result["missing_skills"], ["Java"])
        self.assertEqual(result["matched_soft_skills"], ["团队协作", "沟通"])

    def test_chinese_substrings_do_not_claim_more_specific_abilities(self):
        result = score_role({"current_skills": ["数据", "人事", "沟通"]},
                            self.standard(["数据分析", "人事信息管理", "沟通表达"]))
        self.assertEqual(result["matched_skills"], [])
        self.assertEqual(result["missing_skills"], ["数据分析", "人事信息管理", "沟通表达"])

    def test_more_specific_ability_does_not_match_a_short_ambiguous_label(self):
        result = score_role({"current_skills": ["数据分析", "REST API"]}, self.standard(["数据", "API"]))
        self.assertEqual(result["matched_skills"], [])

    def test_learning_or_negated_prose_is_not_evidence_of_mastery(self):
        result = score_role({"current_skills": ["不会 Java", "计划学习 React", "了解一些 C++"]},
                            self.standard(["Java", "React", "C++"]))
        self.assertEqual(result["matched_skills"], [])
        self.assertEqual(result["missing_skills"], ["Java", "React", "C++"])

    def test_blank_abilities_do_not_produce_a_percentage_even_with_a_target(self):
        for abilities in ([], ["", "  ", "\t"]):
            with self.subTest(abilities=abilities):
                result = score_role({"current_skills": abilities, "soft_skills": abilities,
                                     "target_roles": ["测试岗位"], "interests": ["数据分析"]},
                                    self.standard(["数据分析"], ["团队协作"], description="负责数据分析"))
                self.assertIsNone(result["score"])
                self.assertEqual(result["matched_skills"], [])

    def test_interest_is_kept_separate_from_reported_ability(self):
        result = score_role({"current_skills": ["SQL"], "interests": ["数据分析"]},
                            self.standard(["SQL", "统计分析"], description="负责数据分析和报表"))
        self.assertTrue(result["interest_relevant"])
        self.assertEqual(result["matched_skills"], ["SQL"])
        self.assertEqual(result["missing_skills"], ["统计分析"])

    def test_existing_partial_profile_score_and_role_alias_are_preserved(self):
        result = score_role({"current_skills": ["React"], "soft_skills": ["团队协作"],
                             "target_roles": ["前端工程师"]},
                            self.standard(["React", "TypeScript", "Git"], ["团队协作"], name="前端开发工程师"))
        self.assertTrue(role_matches("前端工程师", "前端开发工程师"))
        self.assertEqual(result["score"], 47)
        self.assertEqual(result["missing_skills"], ["TypeScript", "Git"])


if __name__ == "__main__":
    unittest.main()
