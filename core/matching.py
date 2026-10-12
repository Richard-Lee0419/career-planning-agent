"""Evidence-based role matching shared by recommendations, gap analysis and exports."""

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any


def read_list(value: Any) -> list[str]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            return []
    return [str(item).strip() for item in value if str(item).strip()] if isinstance(value, list) else []


def profile_data(profile: Any) -> dict:
    return {
        "name": profile.name,
        "education_level": profile.education_level,
        "major": profile.major,
        "grade": profile.grade,
        "location": profile.location,
        "current_skills": read_list(profile.current_skills),
        "soft_skills": read_list(profile.soft_skills),
        "certificates": read_list(profile.certificates),
        "target_roles": read_list(profile.target_roles),
        "interests": read_list(profile.interests),
        "internship_experience": profile.internship_experience,
        "weekly_learning_time": getattr(profile, "weekly_learning_time", None),
    }


def _normalized(value: str) -> str:
    value = value.lower().replace("团队合作", "团队协作").replace("沟通协调", "沟通")
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", value)


def role_matches(a: str, b: str) -> bool:
    left, right = _normalized(a), _normalized(b)
    if left == right:
        return True
    # The UI uses “前端工程师”; the role standard says “前端开发工程师”.
    return left.replace("开发", "") == right.replace("开发", "")


# Keys in this small table use NFKC, case-folding and no whitespace. Add aliases
# only when they name the same ability; broad concepts or prerequisites are not
# interchangeable. In particular, C, C++, C# and Java/JavaScript stay distinct.
SKILL_ALIASES = {
    "js": "javascript",
    "ts": "typescript",
    "spring-boot": "springboot",
    "restfulapi": "restapi",
    "团队合作": "团队协作",
    "沟通协调": "沟通",
}


def _plain_skill_key(value: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", value).casefold())


def _canonical_skill_key(value: str) -> str:
    key = _plain_skill_key(value)
    return SKILL_ALIASES.get(key, key)


@lru_cache(maxsize=1)
def _pilot_skill_keys() -> dict[str, str]:
    """Use the reviewed package's small vocabulary; no network or model lookup.

    The importer validates aliases and IDs. A missing package leaves the existing
    exact-name matcher usable, without inventing semantic equivalences.
    """
    path = Path(__file__).resolve().parents[1] / "data" / "pilot_job_standards.json"
    try:
        package = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    ids = package.get("skill_ids", {})
    keys = {_canonical_skill_key(label): skill_id for label, skill_id in ids.items()}
    for label, aliases in package.get("skill_aliases", {}).items():
        if label in ids:
            keys.update({_canonical_skill_key(alias): ids[label] for alias in aliases})
    return keys


def _skill_key(value: str) -> str:
    key = _canonical_skill_key(value)
    vocabulary = _pilot_skill_keys()
    return vocabulary.get(key, key)


def _matches(requirement: str, signals: list[str]) -> bool:
    requirement_key = _skill_key(requirement)
    return bool(requirement_key) and any(_skill_key(signal) == requirement_key for signal in signals)


def _interest_matches(text: str, signals: list[str]) -> bool:
    """Interest keywords may occur in prose; they never establish an ability."""
    requirement_key = _normalized(text)
    if not requirement_key:
        return False
    for signal in signals:
        key = _normalized(signal)
        if len(key) < 2:
            continue
        if key.isascii():
            if re.search(rf"(?<![a-z0-9]){re.escape(key)}(?![a-z0-9])", text.lower()):
                return True
        elif key in requirement_key or (len(requirement_key) >= 3 and requirement_key in key):
            return True
    return False


def score_role(profile: dict, standard: Any) -> dict:
    skills = read_list(standard.core_skills)
    soft = read_list(standard.soft_skills)
    owned_skills = read_list(profile.get("current_skills"))
    owned_soft = read_list(profile.get("soft_skills"))
    matched_skills = [item for item in skills if _matches(item, owned_skills)]
    matched_soft = [item for item in soft if _matches(item, owned_soft)]
    missing_skills = [item for item in skills if item not in matched_skills]
    missing_soft = [item for item in soft if item not in matched_soft]
    preference = any(role_matches(standard.role_name, role) for role in profile.get("target_roles") or [])
    interest = any(_interest_matches(standard.role_name, [item]) or _interest_matches(standard.description or "", [item])
                   for item in read_list(profile.get("interests")))

    # A percentage requires both a job standard and at least one reported ability.
    score = None
    if skills and (owned_skills or owned_soft):
        parts = [(80, len(matched_skills) / len(skills))]
        if soft:
            parts.append((15, len(matched_soft) / len(soft)))
        parts.append((5, 1.0 if preference or interest else 0.0))
        score = round(sum(weight * ratio for weight, ratio in parts) * 100 / sum(weight for weight, _ in parts))

    return {
        "role_name": standard.role_name,
        "score": score,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "matched_soft_skills": matched_soft,
        "missing_soft_skills": missing_soft,
        "target_preference": preference,
        "interest_relevant": interest,
        "evidence": f"基于岗位标准中的 {len(skills)} 项核心技能、{len(soft)} 项软素质，以及你填写的目标与兴趣；未填写的能力不视为已掌握。",
    }
