"""Import a fully validated manual pilot; never overwrite an existing role."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.database import Base, SessionLocal, engine  # noqa: E402
from core.standards import load_pilot_dataset, standard_fingerprint  # noqa: E402
from models.db_models import DBJobStandardMetadata, DBJobStandardProfile  # noqa: E402


def seed_pilot_standards(db, dataset_path=None):
    package = load_pilot_dataset(dataset_path)
    added = 0
    try:
        for item in package.roles:
            if db.query(DBJobStandardProfile).filter_by(role_name=item.role_name).first():
                # Existing profiles may come from a different source. Attaching
                # this package's review would falsely certify their contents.
                continue
            standard = DBJobStandardProfile(
                role_name=item.role_name, description=item.description,
                core_skills=json.dumps(item.core_skills, ensure_ascii=False),
                soft_skills=json.dumps(item.soft_skills, ensure_ascii=False),
                certifications=json.dumps(item.certifications, ensure_ascii=False),
            )
            db.add(standard)
            db.flush()
            metadata = {
                "role_id": item.role_id, "domain": item.domain, "domain_label": item.domain_label,
                "standard_source": item.standard_source.model_dump(mode="json"),
                "fingerprint": standard_fingerprint(standard),
            }
            db.add(DBJobStandardMetadata(standard_id=standard.id,
                metadata_json=json.dumps(metadata, ensure_ascii=False)))
            added += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    return added


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        count = seed_pilot_standards(session)
    print(f"新增 {count} 条人工试点岗位标准；已存在的岗位及来源记录均未覆盖。")
