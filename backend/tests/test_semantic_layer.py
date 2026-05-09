import os
import tempfile
import unittest
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


class SemanticLayerTests(unittest.TestCase):
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
                      region TEXT NOT NULL,
                      status TEXT NOT NULL,
                      amount INTEGER NOT NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO sales (region, status, amount)
                    VALUES
                      ('East', 'paid', 100),
                      ('West', 'paid', 80),
                      ('East', 'pending', 20)
                    """
                )
            )
        source_engine.dispose()
        return path

    def _dataset_fixture(self, source_path: str):
        from app.models.audit_log import AuditLog
        from app.models.dataset import Dataset
        from app.models.datasource import DataSource

        db = self._db([DataSource.__table__, Dataset.__table__, AuditLog.__table__])
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
            name="Sales Semantic Dataset",
            datasource_id=datasource.id,
            fields_json={"table": "sales", "fields": ["sales.region", "sales.status", "sales.amount"]},
            filters_json={"filters": ["sales.status = paid"]},
            semantic_model_json={
                "dimensions": [
                    {"id": "region", "field": "sales.region", "label": "区域"},
                ],
                "metrics": [
                    {"id": "total_amount", "field": "sales.amount", "label": "销售额", "aggregation": "sum"},
                ],
                "time_dimensions": [],
                "synonyms": [{"term": "营收", "target_id": "total_amount"}],
            },
            status="published",
            visibility="org",
            org_id=2,
            owner_id=10,
        )
        db.add(dataset)
        db.commit()
        db.refresh(dataset)
        return db, dataset

    def test_dataset_semantic_model_round_trip_and_validation(self):
        from app.api.datasets import get_dataset_semantic_model, update_dataset_semantic_model
        from app.models.dataset import Dataset
        from app.schemas.dataset import DatasetSemanticModelUpdate

        source_path = self._source_database()
        try:
            db, dataset = self._dataset_fixture(source_path)
            user = SimpleNamespace(id=10, username="owner", role="user", org_id=2)

            response = get_dataset_semantic_model(dataset.id, db=db, current_user=user)
            self.assertEqual(response["semantic_model"]["dimensions"][0]["id"], "region")

            updated = update_dataset_semantic_model(
                dataset.id,
                DatasetSemanticModelUpdate(
                    semantic_model={
                        "dimensions": [{"id": "region", "field": "sales.region", "label": "区域"}],
                        "metrics": [
                            {"id": "avg_amount", "field": "sales.amount", "label": "平均销售额", "aggregation": "avg"}
                        ],
                        "time_dimensions": [],
                        "synonyms": [],
                    }
                ),
                db=db,
                current_user=user,
            )

            self.assertEqual(updated["semantic_model"]["metrics"][0]["id"], "avg_amount")
            self.assertEqual(db.query(Dataset).one().semantic_model_json["metrics"][0]["aggregation"], "avg")
        finally:
            os.unlink(source_path)

    def test_duplicate_semantic_ids_are_rejected(self):
        from app.api.datasets import update_dataset_semantic_model
        from app.schemas.dataset import DatasetSemanticModelUpdate

        source_path = self._source_database()
        try:
            db, dataset = self._dataset_fixture(source_path)
            with self.assertRaises(HTTPException) as exc:
                update_dataset_semantic_model(
                    dataset.id,
                    DatasetSemanticModelUpdate(
                        semantic_model={
                            "dimensions": [
                                {"id": "region", "field": "sales.region", "label": "区域"},
                            ],
                            "metrics": [
                                {"id": "region", "field": "sales.amount", "label": "销售额", "aggregation": "sum"}
                            ],
                        }
                    ),
                    db=db,
                    current_user=SimpleNamespace(id=10, username="owner", role="user", org_id=2),
                )
            self.assertEqual(exc.exception.status_code, 400)
        finally:
            os.unlink(source_path)

    def test_inferred_semantic_model_uses_dataset_dimensions_and_metrics(self):
        from app.api.datasets import get_dataset_semantic_model
        from app.models.dataset import Dataset

        source_path = self._source_database()
        try:
            db, dataset = self._dataset_fixture(source_path)
            dataset.semantic_model_json = None
            dataset.fields_json = {"table": "sales", "dimensions": ["sales.region", "sales.status"]}
            dataset.aggregations_json = {"aggregations": ["SUM(sales.amount)"]}
            db.commit()

            response = get_dataset_semantic_model(
                dataset.id,
                db=db,
                current_user=SimpleNamespace(id=10, username="owner", role="user", org_id=2),
            )

            self.assertEqual([item["id"] for item in response["semantic_model"]["dimensions"]], ["region", "status"])
            self.assertEqual(response["semantic_model"]["metrics"][0]["id"], "sum_amount")

            dataset.fields_json = {
                "table": "sales",
                "dimensions": [{"field": "sales.region", "alias": "区域"}],
                "metrics": [{"field": "sales.amount", "aggregation": "AVG", "alias": "平均销售额"}],
            }
            dataset.aggregations_json = None
            db.commit()

            structured = get_dataset_semantic_model(
                dataset.id,
                db=db,
                current_user=SimpleNamespace(id=10, username="owner", role="user", org_id=2),
            )

            self.assertEqual(structured["semantic_model"]["dimensions"][0]["label"], "区域")
            self.assertEqual(structured["semantic_model"]["metrics"][0]["label"], "平均销售额")
            self.assertEqual(structured["semantic_model"]["metrics"][0]["aggregation"], "avg")
        finally:
            os.unlink(source_path)

    def test_semantic_query_executes_dataset_scoped_metric(self):
        from app.api.query import semantic_query
        from app.schemas.query import SemanticQueryRequest

        source_path = self._source_database()
        try:
            db, dataset = self._dataset_fixture(source_path)
            response = semantic_query(
                SemanticQueryRequest(
                    dataset_id=dataset.id,
                    dimensions=["region"],
                    metrics=["total_amount"],
                    limit=20,
                ),
                db=db,
                current_user=SimpleNamespace(id=99, username="analyst", role="user", org_id=2),
            )

            self.assertEqual(response["columns"], ["region", "total_amount"])
            self.assertEqual(response["labels"], {"region": "区域", "total_amount": "销售额"})
            self.assertEqual(
                response["rows"],
                [
                    {"region": "East", "total_amount": 100},
                    {"region": "West", "total_amount": 80},
                ],
            )
            self.assertIn("GROUP BY", response["sql_query"])
            self.assertIn("sales.status", response["sql_query"])
        finally:
            os.unlink(source_path)


if __name__ == "__main__":
    unittest.main()
