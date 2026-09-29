"""Demo standards make a clean local checkout usable without inventing job postings."""

import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from core.database import Base
from models.db_models import DBJobStandardProfile
from scripts.seed_demo_data import seed_demo_standards


class DemoSeedTests(unittest.TestCase):
    def test_seed_is_labeled_and_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            engine = create_engine(f"sqlite:///{Path(temp) / 'demo.db'}")
            try:
                Base.metadata.create_all(bind=engine)
                with Session(engine) as db:
                    self.assertEqual(seed_demo_standards(db), 4)
                    self.assertEqual(seed_demo_standards(db), 0)
                    self.assertEqual(db.scalar(select(func.count()).select_from(DBJobStandardProfile)), 4)
                    standards = db.scalars(select(DBJobStandardProfile)).all()
                    self.assertTrue(all(item.description.startswith("演示用岗位标准") for item in standards))
            finally:
                engine.dispose()
