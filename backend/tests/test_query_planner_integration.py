import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


class QueryPlannerIntegrationTests(unittest.TestCase):
    def test_generate_safe_sql_passes_query_plan_into_sql_generation(self):
        from app.api.query import _generate_safe_sql

        datasource = SimpleNamespace(
            source_type="excel",
            database_url="/tmp/fake.xlsx",
        )
        plan = {"query_type": "detail"}

        with patch(
            "app.api.query.generate_sql_query",
            new=AsyncMock(return_value={"sql": "SELECT * FROM ngtype"}),
        ) as mocked_generate, patch(
            "app.api.query.detect_excel_join_risk",
            return_value=None,
        ):
            sql = asyncio.run(_generate_safe_sql("列出明细", datasource, plan))

        self.assertEqual(sql, "SELECT * FROM ngtype")
        _, kwargs = mocked_generate.await_args
        self.assertEqual(kwargs["query_plan"], plan)

    def test_generate_safe_sql_passes_metric_match_into_sql_generation(self):
        from app.api.query import _generate_safe_sql

        datasource = SimpleNamespace(
            source_type="postgres",
            database_url="postgresql://example",
        )
        metric_match = {
            "name": "良率",
            "formula": "SUM(good_qty) / SUM(output_qty)",
        }

        with patch(
            "app.api.query.generate_sql_query",
            new=AsyncMock(return_value={"sql": "SELECT SUM(good_qty) / SUM(output_qty) AS 良率 FROM prod"}),
        ) as mocked_generate, patch(
            "app.api.query.detect_excel_join_risk",
            return_value=None,
        ):
            sql = asyncio.run(_generate_safe_sql("查询良率", datasource, metric_match=metric_match))

        self.assertIn("SUM(good_qty) / SUM(output_qty)", sql)
        _, kwargs = mocked_generate.await_args
        self.assertEqual(kwargs["metric_match"], metric_match)


if __name__ == "__main__":
    unittest.main()
