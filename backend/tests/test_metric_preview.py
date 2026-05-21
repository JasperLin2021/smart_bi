import os
import tempfile
import unittest
from types import SimpleNamespace

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


class MetricPreviewTests(unittest.TestCase):
    def _db(self, tables):
        from app.db.base_class import Base

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine, tables=tables)
        return sessionmaker(bind=engine)()

    def _source_database(self):
        fd, path = tempfile.mkstemp(prefix="metric-preview-", suffix=".db")
        os.close(fd)
        engine = create_engine(f"sqlite:///{path}")
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE sales (
                      id INTEGER PRIMARY KEY,
                      region TEXT NOT NULL,
                      status TEXT NOT NULL,
                      amount REAL NOT NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO sales (region, status, amount)
                    VALUES
                      ('华东', '已完成', 120),
                      ('华东', '已完成', 50),
                      ('华东', '已退款', 999),
                      ('华南', '已完成', 80)
                    """
                )
            )
        engine.dispose()
        return path

    def test_metric_preview_groups_live_data_by_selected_dimension(self):
        from app.api.metrics import preview_metric
        from app.models.dataset import Dataset
        from app.models.datasource import DataSource
        from app.models.metric import Metric
        from app.schemas.metric import MetricPreviewRequest

        source_path = self._source_database()
        try:
            db = self._db([DataSource.__table__, Dataset.__table__, Metric.__table__])
            datasource = DataSource(
                name="销售库",
                slug="sales-preview",
                source_type="database",
                database_url=f"sqlite:///{source_path}",
                metadata_prompt="",
                org_id=2,
            )
            db.add(datasource)
            db.flush()
            dataset = Dataset(
                name="销售订单",
                datasource_id=datasource.id,
                fields_json={
                    "table": "sales",
                    "dimensions": [{"name": "sales.region", "alias": "大区", "type": "string"}],
                    "metrics": [{"name": "sales.amount", "alias": "订单金额", "type": "decimal", "aggregation": "sum"}],
                },
                status="published",
                visibility="org",
                org_id=2,
                owner_id=10,
            )
            db.add(dataset)
            db.flush()
            metric = Metric(
                dataset_id=dataset.id,
                datasource_id=datasource.id,
                name="完成订单销售额",
                definition="已完成订单金额合计",
                formula="SUM(sales.amount)",
                column_name="sales.amount",
                aggregation="sum",
                calculation_config={
                    "calculation_mode": "aggregate",
                    "metric_field": "sales.amount",
                    "filters": [{"logic": "AND", "field": "sales.status", "operator": "=", "value": "已完成"}],
                },
                status="published",
                certification_status="certified",
                quality_status="normal",
            )
            db.add(metric)
            db.commit()
            db.refresh(metric)

            result = preview_metric(
                metric.id,
                MetricPreviewRequest(dimensions=["sales.region"], limit=10),
                db=db,
                current_user=SimpleNamespace(id=11, username="analyst", role="org_admin", org_id=2),
            )

            self.assertEqual(result["columns"], ["大区", "完成订单销售额"])
            self.assertEqual(result["rows"], [{"大区": "华东", "完成订单销售额": 170.0}, {"大区": "华南", "完成订单销售额": 80.0}])
            self.assertEqual(result["row_count"], 2)
            self.assertEqual(result["metric"]["name"], "完成订单销售额")
            self.assertEqual(result["query"]["dimensions"], ["sales.region"])
            self.assertIn("GROUP BY", result["query"]["sql"])
            self.assertIn("WHERE", result["query"]["sql"])
        finally:
            os.unlink(source_path)


if __name__ == "__main__":
    unittest.main()
