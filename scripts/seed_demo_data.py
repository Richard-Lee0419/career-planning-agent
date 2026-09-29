"""为全新本地安装添加明确标注的演示岗位标准；不写入虚构招聘信息。"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.database import Base, SessionLocal, engine  # noqa: E402
from models.db_models import DBJobStandardProfile  # noqa: E402

DEMO_DATA = ROOT / "data" / "demo_job_standards.json"


def seed_demo_standards(db):
    records = json.loads(DEMO_DATA.read_text(encoding="utf-8"))
    added = 0
    for item in records:
        if db.query(DBJobStandardProfile).filter_by(role_name=item["role_name"]).first():
            continue
        db.add(DBJobStandardProfile(
            role_name=item["role_name"],
            description=item["description"],
            core_skills=json.dumps(item["core_skills"], ensure_ascii=False),
            soft_skills=json.dumps(item["soft_skills"], ensure_ascii=False),
            certifications=json.dumps(item["certifications"], ensure_ascii=False),
        ))
        added += 1
    db.commit()
    return added


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        count = seed_demo_standards(session)
    print(f"新增 {count} 条演示岗位标准；已存在的岗位未覆盖。")
