import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


class MetricBindingTests(unittest.TestCase):
    def test_match_metric_from_question_prefers_exact_name(self):
        from app.core.metric_binding import match_metric_from_question

        datasource = SimpleNamespace(
            metrics_prompt="可用指标：\n- 总产出: 计算公式：SUM(output_qty)\n- 良率: 计算公式：SUM(good_qty) / SUM(output_qty)"
        )

        matched = match_metric_from_question("请看今天的良率趋势", datasource)

        self.assertIsNotNone(matched)
        self.assertEqual(matched["name"], "良率")
        self.assertEqual(matched["formula"], "SUM(good_qty) / SUM(output_qty)")

    def test_generate_safe_sql_retries_when_target_metric_formula_missing(self):
        from app.api.query import _generate_safe_sql

        datasource = SimpleNamespace(
            source_type="postgres",
            database_url="postgresql://example",
        )
        metric_match = {
            "name": "良率",
            "formula": "SUM(good_qty) / SUM(output_qty)",
        }
        first_sql = "SELECT COUNT(*) AS 良率 FROM prod"
        second_sql = "SELECT SUM(good_qty) / SUM(output_qty) AS 良率 FROM prod"

        with patch(
            "app.api.query.generate_sql_query",
            new=AsyncMock(side_effect=[{"sql": first_sql}, {"sql": second_sql}]),
        ) as mocked_generate, patch(
            "app.api.query.detect_excel_join_risk",
            return_value=None,
        ):
            sql = asyncio.run(_generate_safe_sql("查询良率", datasource, metric_match=metric_match))

        self.assertEqual(sql, second_sql)
        self.assertEqual(mocked_generate.await_count, 2)
        _, second_kwargs = mocked_generate.await_args_list[1]
        self.assertIn("没有使用目标指标", second_kwargs["context"])

    def test_generate_safe_sql_raises_when_metric_formula_still_missing(self):
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
            new=AsyncMock(side_effect=[{"sql": "SELECT COUNT(*) FROM prod"}, {"sql": "SELECT AVG(score) FROM prod"}]),
        ), patch(
            "app.api.query.detect_excel_join_risk",
            return_value=None,
        ):
            with self.assertRaises(ValueError) as ctx:
                asyncio.run(_generate_safe_sql("查询良率", datasource, metric_match=metric_match))

        self.assertIn("目标指标公式", str(ctx.exception))

    def test_sql_uses_metric_formula_accepts_equivalent_join_filter_sql(self):
        from app.core.metric_binding import sql_uses_metric_formula

        formula = (
            "SUM(production.OKCOUNT) "
            "WHERE production.MAINID IN "
            "(SELECT ID FROM mainrecord WHERE LINE = 'REPS3 Final')"
        )
        sql = (
            "SELECT SUM(p.OKCOUNT) AS 线产出 "
            "FROM production p "
            "JOIN mainrecord m ON p.MAINID = m.ID "
            "WHERE m.LINE = 'REPS3 Final'"
        )

        self.assertTrue(sql_uses_metric_formula(sql, formula))


if __name__ == "__main__":
    unittest.main()
