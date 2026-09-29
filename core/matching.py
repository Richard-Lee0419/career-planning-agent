"""Evidence-based role matching shared by recommendations, gap analysis and exports."""

import json
import re
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


def _matches(requirement: str, signals: list[str]) -> bool:
    requirement_key = _normalized(requirement)
    if not requirement_key:
        return False
    for signal in signals:
        key = _normalized(signal)
        if len(key) < 2:
            continue
        if key.isascii():
            if re.search(rf"(?<![a-z0-9]){re.escape(key)}(?![a-z0-9])", requirement.lower()):
                return True
        elif key in requirement_key or (len(requirement_key) >= 3 and requirement_key in key):
            return True
    return False


def score_role(profile: dict, standard: Any) -> dict:
    skills = read_list(standard.core_skills)
    soft = read_list(standard.soft_skills)
    owned_skills = profile.get("current_skills") or []
    owned_soft = profile.get("soft_skills") or []
    matched_skills = [item for item in skills if _matches(item, owned_skills)]
    matched_soft = [item for item in soft if _matches(item, owned_soft)]
    missing_skills = [item for item in skills if item not in matched_skills]
    missing_soft = [item for item in soft if item not in matched_soft]
    preference = any(role_matches(standard.role_name, role) for role in profile.get("target_roles") or [])
    interest = any(_matches(standard.role_name, [item]) or _matches(standard.description or "", [item])
                   for item in profile.get("interests") or [])

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
