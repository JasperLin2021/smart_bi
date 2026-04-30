import os
import tempfile
import unittest
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


class DatasetPipelineTests(unittest.TestCase):
    def _db(self, tables):
        from app.db.base_class import Base
        from app.models.organization import Organization  # noqa: F401

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine, tables=tables)
        return sessionmaker(bind=engine)()

    def _source_database(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        source_engine = create_engine(f"sqlite:///{path}")
        with source_engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE sales (
                      id INTEGER PRIMARY KEY,
                      region TEXT NOT NULL,
                      category TEXT NOT NULL,
                      amount INTEGER NOT NULL,
                      cost INTEGER NOT NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO sales (region, category, amount, cost)
                    VALUES
                      ('East', 'A', 100, 70),
                      ('West', 'A', 80, 50),
                      ('East', 'B', 130, 90)
                    """
                )
            )
        source_engine.dispose()
        return path

    def _dataset_fixture(self, source_path: str):
        from app.models.audit_log import AuditLog
        from app.models.dataset import Dataset, DatasetRefreshLog
        from app.models.datasource import DataSource

        db = self._db([DataSource.__table__, Dataset.__table__, DatasetRefreshLog.__table__, AuditLog.__table__])
        datasource = DataSource(
            name="Sales DB",
            slug="sales-db",
            source_type="database",
            database_url=f"sqlite:///{source_path}",
            metadata_prompt="",
            org_id=2,
        )
        db.add(datasource)
        db.flush()
        dataset = Dataset(
            name="East Sales",
            datasource_id=datasource.id,
            fields_json={"table": "sales", "fields": ["sales.region", "sales.amount"]},
            filters_json={"filters": ["sales.region = East"]},
            derived_columns_json={"expressions": ["margin = sales.amount - sales.cost"]},
            status="draft",
            visibility="private",
            org_id=2,
            owner_id=10,
        )
        db.add(dataset)
        db.commit()
        db.refresh(dataset)
        return db, dataset

    def test_dataset_preview_executes_selected_fields_filters_and_derived_columns(self):
        from app.api.datasets import preview_dataset
        from app.schemas.dataset import DatasetPreviewRequest

        source_path = self._source_database()
        try:
            db, dataset = self._dataset_fixture(source_path)
            result = preview_dataset(
                dataset.id,
                DatasetPreviewRequest(limit=10),
                db=db,
                current_user=SimpleNamespace(id=10, username="owner", role="user", org_id=2),
            )

            self.assertEqual(result["columns"], ["region", "amount", "margin"])
            self.assertEqual(
                result["rows"],
                [
                    {"region": "East", "amount": 100, "margin": 30},
                    {"region": "East", "amount": 130, "margin": 40},
                ],
            )
            self.assertEqual(result["dataset_id"], dataset.id)
        finally:
            os.unlink(source_path)

    def test_dataset_preview_is_scoped_to_user_org(self):
        from app.api.datasets import preview_dataset
        from app.schemas.dataset import DatasetPreviewRequest

        source_path = self._source_database()
        try:
            db, dataset = self._dataset_fixture(source_path)
            with self.assertRaises(HTTPException) as exc:
                preview_dataset(
                    dataset.id,
                    DatasetPreviewRequest(limit=10),
                    db=db,
                    current_user=SimpleNamespace(id=99, username="other", role="org_admin", org_id=3),
                )
            self.assertEqual(exc.exception.status_code, 404)
        finally:
            os.unlink(source_path)

    def test_dataset_refresh_writes_log_and_updates_dataset_status(self):
        from app.api.datasets import list_dataset_refresh_logs, refresh_dataset
        from app.models.dataset import DatasetRefreshLog

        source_path = self._source_database()
        try:
            db, dataset = self._dataset_fixture(source_path)
            user = SimpleNamespace(id=10, username="owner", role="user", org_id=2)

            result = refresh_dataset(dataset.id, db=db, current_user=user)
            logs = list_dataset_refresh_logs(dataset.id, db=db, current_user=user)

            self.assertEqual(result.status, "success")
            self.assertEqual(result.row_count, 2)
            self.assertEqual(dataset.last_refresh_status, "success")
            self.assertEqual(dataset.last_refresh_row_count, 2)
            self.assertIsNotNone(dataset.last_refresh_at)
            self.assertEqual(len(logs["items"]), 1)
            self.assertEqual(db.query(DatasetRefreshLog).count(), 1)
        finally:
            os.unlink(source_path)


if __name__ == "__main__":
    unittest.main()
