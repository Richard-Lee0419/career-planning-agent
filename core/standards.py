"""Validated pilot standards and source records; occupation data is not job ads."""

import hashlib
import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints, model_validator

from core.matching import role_matches
from models.db_models import DBJobStandardMetadata


ROOT = Path(__file__).resolve().parents[1]
PILOT_DATA = ROOT / "data" / "pilot_job_standards.json"
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, strict=True)]


class ValidatedRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PilotDomain(ValidatedRecord):
    id: Text
    label: Text


class StandardSourceReference(ValidatedRecord):
    title: Text
    url: HttpUrl
    kind: Literal["education_standard", "employer_example"]
    published_at: Text | None = None
    evidence_location: str = ""
    accessed_at: date | None = None
    access_status: Text = "正文已核对"


class PilotStandardSource(ValidatedRecord):
    type: Literal["manual_pilot"]
    version: Text
    region: Literal["中国大陆"]
    review_status: Literal["source_checked"]
    reviewed_at: date
    sources: list[StandardSourceReference] = Field(..., min_length=1)
    limitations: list[Text] = Field(..., min_length=1)
    tasks: list[Text] = Field(..., min_length=1)


class PilotRole(ValidatedRecord):
    role_id: Text
    role_name: Text
    domain: Text
    domain_label: Text
    description: Text
    core_skills: list[Text] = Field(..., min_length=1)
    soft_skills: list[Text]
    certifications: list[Text]
    standard_source: PilotStandardSource


class PilotDataset(ValidatedRecord):
    schema_version: Literal["1.0"]
    version: Text
    domains: list[PilotDomain] = Field(..., min_length=1)
    roles: list[PilotRole] = Field(..., min_length=1)
    skill_aliases: dict[Text, list[Text]] = Field(default_factory=dict)
    skill_ids: dict[Text, Text] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_relationships(self):
        domain_labels = {item.id: item.label for item in self.domains}
        if len(domain_labels) != len(self.domains):
            raise ValueError("领域 ID 必须唯一")
        if len({item.role_id for item in self.roles}) != len(self.roles):
            raise ValueError("岗位 ID 必须唯一")
        if len({item.role_name for item in self.roles}) != len(self.roles):
            raise ValueError("岗位名称必须唯一")
        if len(set(self.skill_ids.values())) != len(self.skill_ids):
            raise ValueError("技能 ID 必须唯一")
        known_skills = {skill for role in self.roles for skill in (*role.core_skills, *role.soft_skills)}
        if set(self.skill_ids) - known_skills:
            raise ValueError("技能 ID 的名称必须出现在数据包的核心或软技能中")
        if set(self.skill_aliases) - set(self.skill_ids):
            raise ValueError("每个技能别名的规范名称都必须有技能 ID")
        alias_owners = {}
        for canonical in self.skill_ids:
            for label in (canonical, *self.skill_aliases.get(canonical, [])):
                key = re.sub(r"\s+", "", unicodedata.normalize("NFKC", label).casefold())
                previous = alias_owners.setdefault(key, canonical)
                if previous != canonical:
                    raise ValueError("同一个技能名称或别名不能映射到不同规范名称")
        for role in self.roles:
            if domain_labels.get(role.domain) != role.domain_label:
                raise ValueError("岗位领域及标签必须与领域目录一致")
            if role.standard_source.version != self.version:
                raise ValueError("岗位来源版本必须与数据包版本一致")
        return self


class StoredStandardMetadata(ValidatedRecord):
    role_id: Text
    domain: Text
    domain_label: Text
    standard_source: PilotStandardSource
    fingerprint: Text


def load_pilot_dataset(path=None) -> PilotDataset:
    """Validate the entire package before a caller changes any database rows."""
    return PilotDataset.model_validate_json(Path(path or PILOT_DATA).read_text(encoding="utf-8"))


def standard_fingerprint(standard) -> str:
    fields = {"role_name": standard.role_name, "description": standard.description}
    for key in ("core_skills", "soft_skills", "certifications"):
        value = getattr(standard, key)
        try:
            fields[key] = json.loads(value) if isinstance(value, str) else value
        except (TypeError, ValueError):
            fields[key] = value
    content = json.dumps(fields, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


KNOWN_TECH_ROLES = (
    "前端开发工程师", "Java后端开发", "Java 后端开发工程师", "UI/UX设计师", "产品经理",
    "软件测试工程师", "数据分析师", "算法工程师", "运维工程师", "项目经理", "全栈工程师",
    "架构师", "技术总监", "数据产品经理", "移动端开发工程师", "交互设计师",
)


def _unmanaged_metadata(standard) -> dict:
    demo = (standard.description or "").startswith("演示用岗位标准")
    known_technology = any(role_matches(standard.role_name or "", name) for name in KNOWN_TECH_ROLES)
    domain = "technology" if known_technology else "unclassified"
    source_type = "demo_example" if demo else "legacy_unverified"
    explanation = (
        "本标准为公开运行示例，未由招聘样本统计得出，不代表真实招聘要求或效果验证。"
        if demo else "既有岗位标准尚未建立可核验来源链，不能宣称由招聘样本统计或人工审核得出。"
    )
    role_key = hashlib.sha256((standard.role_name or "").encode("utf-8")).hexdigest()[:12]
    return {
        "role_id": f"{source_type}-{role_key}",
        "domain": domain,
        "domain_label": "技术与产品" if domain == "technology" else "未分类岗位",
        "standard_source": {
            "type": source_type, "version": None, "region": "未核实", "review_status": "unverified",
            "reviewed_at": None, "sources": [], "limitations": [explanation], "tasks": [],
        },
    }


def standard_metadata(db, standard) -> dict:
    """Read source records without granting an old review to a modified standard."""
    row = db.get(DBJobStandardMetadata, standard.id) if standard.id is not None else None
    if row is None:
        return _unmanaged_metadata(standard)
    try:
        stored = StoredStandardMetadata.model_validate_json(row.metadata_json)
    except (TypeError, ValueError):
        result = _unmanaged_metadata(standard)
        result["standard_source"]["limitations"].append("关联来源记录格式无效，无法核实审核状态。")
        return result
    result = stored.model_dump(mode="json", exclude={"fingerprint"})
    if stored.fingerprint != standard_fingerprint(standard):
        result["standard_source"]["review_status"] = "modified_unverified"
        result["standard_source"]["limitations"].append(
            "当前标准内容已偏离来源审核时的版本；所列来源仅对应原版本，当前内容需重新审核。"
        )
    return result
