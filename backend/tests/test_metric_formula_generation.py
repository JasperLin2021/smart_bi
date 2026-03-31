import asyncio
import unittest
from unittest.mock import AsyncMock, patch


class MetricFormulaGenerationTests(unittest.TestCase):
    def test_generate_metric_formula_uses_datasource_context(self):
        from app.core.metric_formula import generate_metric_formula

        datasource_context = {
            "name": "嘉盛半导体",
            "metadata_prompt": "detail 表包含 count 字段",
            "schema_metadata": {"tables": [{"name": "detail", "columns": [{"name": "count", "type": "INTEGER"}]}]},
        }

        with patch("app.core.metric_formula.chat_completion", new=AsyncMock(return_value="SUM(count)")) as mocked:
            formula = asyncio.run(
                generate_metric_formula(
                    datasource_context=datasource_context,
                    name="异常数量",
                    definition="统计异常记录数量",
                    table_name="detail",
                    column_name="count",
                )
            )

        self.assertEqual(formula, "SUM(count)")
        mocked.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
