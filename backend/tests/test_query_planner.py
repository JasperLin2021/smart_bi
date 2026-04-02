import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


class QueryPlannerTests(unittest.TestCase):
    def test_plan_query_classifies_detail_with_rules(self):
        from app.core.query_planner import plan_query

        datasource = SimpleNamespace(metadata_prompt="", metrics_prompt="")
        plan = asyncio.run(plan_query("列出 OP100A 工位的详细记录", datasource))

        self.assertEqual(plan["query_type"], "detail")
        self.assertTrue(plan["detail_preferred"])
        self.assertEqual(plan["chart_preference"], "table")

    def test_plan_query_classifies_distribution_with_rules(self):
        from app.core.query_planner import plan_query

        datasource = SimpleNamespace(metadata_prompt="", metrics_prompt="")
        plan = asyncio.run(plan_query("不同工站的不良数量分布是怎样的", datasource))

        self.assertEqual(plan["query_type"], "distribution")
        self.assertEqual(plan["aggregation"], "grouped_metric")

    def test_plan_query_classifies_ranking_with_rules(self):
        from app.core.query_planner import plan_query

        datasource = SimpleNamespace(metadata_prompt="", metrics_prompt="")
        plan = asyncio.run(plan_query("今天 OEE 最低的 5 个产品型号", datasource))

        self.assertEqual(plan["query_type"], "ranking")
        self.assertEqual(plan["chart_preference"], "bar")

    def test_plan_query_uses_llm_fallback_when_rules_unclear(self):
        from app.core.query_planner import plan_query

        datasource = SimpleNamespace(metadata_prompt="表结构", metrics_prompt="指标")
        raw = """
        {
          "query_type": "aggregate",
          "primary_table": "mainrecord",
          "dimensions": ["LINE"],
          "metrics": ["AVG(OEE)"],
          "aggregation": "grouped_metric",
          "time_intent": false,
          "needs_join": false,
          "detail_preferred": false,
          "chart_preference": "bar"
        }
        """

        with patch("app.core.query_planner.chat_completion", new=AsyncMock(return_value=raw)):
            plan = asyncio.run(plan_query("帮我分析一下产线表现", datasource))

        self.assertEqual(plan["query_type"], "aggregate")
        self.assertEqual(plan["primary_table"], "mainrecord")


if __name__ == "__main__":
    unittest.main()
