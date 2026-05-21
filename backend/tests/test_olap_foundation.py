import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


class OlapFoundationTests(unittest.TestCase):
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
                      updated_at TEXT NOT NULL,
                      region TEXT NOT NULL,
                      amount INTEGER NOT NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO sales (updated_at, region, amount)
                    VALUES
                      ('2026-05-01 00:00:00', 'East', 100),
                      ('2026-05-02 00:00:00', 'West', 80)
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
            name="Sales Dataset",
            datasource_id=datasource.id,
            fields_json={"table": "sales", "fields": ["sales.id", "sales.updated_at", "sales.region", "sales.amount"]},
            status="published",
            visibility="org",
            org_id=2,
            owner_id=10,
        )
        db.add(dataset)
        db.commit()
        db.refresh(dataset)
        return db, dataset

    def test_doris_sqlalchemy_url_uses_mysql_protocol(self):
        from app.core.olap import build_doris_sqlalchemy_url

        config = SimpleNamespace(
            doris_host="doris-fe",
            doris_query_port=9030,
            doris_user="root",
            doris_password="pa ss",
            doris_database="smart_bi_olap",
        )

        self.assertEqual(
            build_doris_sqlalchemy_url(config),
            "mysql+pymysql://root:pa+ss@doris-fe:9030/smart_bi_olap",
        )

    def test_dataset_schema_exposes_materialization_fields(self):
        from app.models.organization import Organization  # noqa: F401
        from app.models.dataset import Dataset
        from app.schemas.dataset import DatasetOut

        dataset = Dataset(
            id=7,
            name="Certified Sales",
            datasource_id=3,
            status="published",
            visibility="org",
            last_refresh_row_count=0,
            materialization_status="ready",
            materialization_mode="incremental",
            materialized_table_name="sb_org_2_dataset_7",
            incremental_key="updated_at",
            incremental_watermark="2026-05-02 00:00:00",
            materialization_message="2 rows written",
        )

        payload = DatasetOut.model_validate(dataset)

        self.assertEqual(payload.materialization_status, "ready")
        self.assertEqual(payload.materialization_mode, "incremental")
        self.assertEqual(payload.materialized_table_name, "sb_org_2_dataset_7")
        self.assertEqual(payload.incremental_key, "updated_at")
        self.assertEqual(payload.incremental_watermark, "2026-05-02 00:00:00")
        self.assertEqual(payload.materialization_message, "2 rows written")

    def test_dataset_schema_accepts_list_join_config(self):
        from app.models.organization import Organization  # noqa: F401
        from app.models.dataset import Dataset
        from app.schemas.dataset import DatasetOut

        dataset = Dataset(
            id=8,
            name="Sales Join Dataset",
            datasource_id=3,
            joins_json=[
                {"right": "customers", "type": "LEFT JOIN", "on": "orders.customer_id = customers.customer_id"},
                {"right": "order_items", "type": "LEFT JOIN", "on": "orders.order_id = order_items.order_id"},
            ],
            status="published",
            visibility="org",
            last_refresh_row_count=0,
        )

        payload = DatasetOut.model_validate(dataset)

        self.assertEqual(payload.joins_json["joins"][0]["right"], "customers")

    def test_materialize_dataset_updates_state_and_logs_refresh(self):
        from app.api.datasets import materialize_dataset
        from app.core.olap import OlapWriteResult
        from app.models.dataset import DatasetRefreshLog
        from app.schemas.dataset import DatasetMaterializeRequest

        source_path = self._source_database()
        try:
            db, dataset = self._dataset_fixture(source_path)
            user = SimpleNamespace(id=10, username="owner", role="user", org_id=2)
            write_result = OlapWriteResult(
                table_name="sb_org_2_dataset_1",
                row_count=2,
                mode="full",
                watermark="2026-05-02 00:00:00",
                message="2 rows materialized",
            )

            with patch("app.api.datasets.settings.doris_enabled", True), patch(
                "app.api.datasets.write_dataset_to_olap",
                return_value=write_result,
            ) as mocked_write:
                result = materialize_dataset(
                    dataset.id,
                    DatasetMaterializeRequest(mode="full", incremental_key="updated_at"),
                    db=db,
                    current_user=user,
                )

            mocked_write.assert_called_once()
            self.assertEqual(result.materialization_status, "ready")
            self.assertEqual(result.materialization_mode, "full")
            self.assertEqual(result.materialized_table_name, "sb_org_2_dataset_1")
            self.assertEqual(result.incremental_key, "updated_at")
            self.assertEqual(result.incremental_watermark, "2026-05-02 00:00:00")
            self.assertEqual(result.last_refresh_status, "success")
            self.assertEqual(db.query(DatasetRefreshLog).count(), 1)
        finally:
            os.unlink(source_path)

    def test_preview_prefers_materialized_table_when_dataset_is_ready(self):
        from app.api.datasets import preview_dataset
        from app.schemas.dataset import DatasetPreviewRequest

        source_path = self._source_database()
        try:
            db, dataset = self._dataset_fixture(source_path)
            dataset.materialization_status = "ready"
            dataset.materialized_table_name = "sb_org_2_dataset_1"
            db.commit()

            with patch("app.api.datasets.settings.doris_enabled", True), patch(
                "app.api.datasets.execute_materialized_dataset_preview",
                return_value={"columns": ["region", "amount"], "rows": [{"region": "East", "amount": 100}]},
            ) as mocked_preview:
                result = preview_dataset(
                    dataset.id,
                    DatasetPreviewRequest(limit=10),
                    db=db,
                    current_user=SimpleNamespace(id=10, username="owner", role="user", org_id=2),
                )

            mocked_preview.assert_called_once_with("sb_org_2_dataset_1", 10)
            self.assertEqual(result["columns"], ["region", "amount"])
            self.assertEqual(result["rows"], [{"region": "East", "amount": 100}])
        finally:
            os.unlink(source_path)


if __name__ == "__main__":
    unittest.main()
