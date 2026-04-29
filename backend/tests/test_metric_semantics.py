import unittest
from types import SimpleNamespace
from unittest.mock import patch


class MetricSemanticsTests(unittest.TestCase):
    def test_create_metric_preserves_semantic_fields(self):
        from app.api.metrics import create_metric
        from app.models.datasource import DataSource
        from app.models.metric import Metric
        from app.models.organization import Organization  # noqa: F401
        from app.schemas.metric import MetricCreate

        created = {}
        datasource = SimpleNamespace(id=7)

        class FakeQuery:
            def __init__(self, model):
                self.model = model

            def filter(self, *_args, **_kwargs):
                return self

            def first(self):
                if self.model is DataSource:
                    return datasource
                return None

        class FakeDb:
            def query(self, model):
                return FakeQuery(model)

            def add(self, row):
                created["row"] = row

            def commit(self):
                return None

            def refresh(self, row):
                row.id = 1

        payload = MetricCreate(
            datasource_id=7,
            name="良率",
            description="质量指标",
            definition="良品数 / 总产出",
            table_name="production",
            column_name="good_qty",
            formula="SUM(good_qty) / SUM(output_qty)",
            owner_name="质量部",
            unit="%",
            aggregation="ratio",
            tags=["质量", "核心指标"],
            status="published",
            dimensions=["line", "product"],
        )

        with patch("app.api.metrics.sync_datasource_metrics_prompt"):
            result = create_metric(
                payload,
                db=FakeDb(),
                current_user=SimpleNamespace(role="super_admin"),
            )

        self.assertIsInstance(created["row"], Metric)
        self.assertEqual(created["row"].owner_name, "质量部")
        self.assertEqual(created["row"].unit, "%")
        self.assertEqual(created["row"].aggregation, "ratio")
        self.assertEqual(created["row"].tags, ["质量", "核心指标"])
        self.assertEqual(created["row"].dimensions, ["line", "product"])
        self.assertEqual(result.status, "published")


if __name__ == "__main__":
    unittest.main()
