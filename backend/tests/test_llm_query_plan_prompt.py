import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch


class LlmQueryPlanPromptTests(unittest.TestCase):
    def test_generate_sql_query_adds_excel_value_matching_guidance(self):
        from app.core.llm import generate_sql_query

        datasource = SimpleNamespace(
            source_type="excel",
            metadata_prompt="metadata",
            metrics_prompt="metrics",
            text2sql_prompt="base",
        )

        async def fake_chat_completion(messages, temperature=0.2, config_override=None):
            system_prompt = messages[0]["content"]
            self.assertIn("优先直接用该字段做等值过滤", system_prompt)
            self.assertIn("不要把一个完整的产线名", system_prompt)
            self.assertIn("不要臆造该列的筛选条件", system_prompt)
            return "SELECT * FROM ngtype"

        with patch("app.core.llm.chat_completion", new=fake_chat_completion):
            result = asyncio.run(generate_sql_query("查看 MPP REPS-4th FC 单元的异常分布", datasource=datasource))

        self.assertEqual(result["sql"], "SELECT * FROM ngtype")

    def test_generate_sql_query_adds_detail_plan_guidance(self):
        from app.core.llm import generate_sql_query

        datasource = SimpleNamespace(
            source_type="excel",
            metadata_prompt="metadata",
            metrics_prompt="metrics",
            text2sql_prompt="base",
        )
        plan = {"query_type": "detail"}

        async def fake_chat_completion(messages, temperature=0.2, config_override=None):
            self.assertIn("当前查询规划类型：detail", messages[0]["content"])
            self.assertIn("优先返回明细记录", messages[0]["content"])
            return "SELECT * FROM ngtype"

        with patch("app.core.llm.chat_completion", new=fake_chat_completion):
            result = asyncio.run(generate_sql_query("列出明细", datasource=datasource, query_plan=plan))

        self.assertEqual(result["sql"], "SELECT * FROM ngtype")

    def test_generate_sql_query_adds_ranking_plan_guidance(self):
        from app.core.llm import generate_sql_query

        datasource = SimpleNamespace(
            source_type="excel",
            metadata_prompt="metadata",
            metrics_prompt="metrics",
            text2sql_prompt="base",
        )
        plan = {"query_type": "ranking"}

        async def fake_chat_completion(messages, temperature=0.2, config_override=None):
            self.assertIn("当前查询规划类型：ranking", messages[0]["content"])
            self.assertIn("必须显式排序", messages[0]["content"])
            return "SELECT x FROM t ORDER BY y DESC"

        with patch("app.core.llm.chat_completion", new=fake_chat_completion):
            result = asyncio.run(generate_sql_query("排名", datasource=datasource, query_plan=plan))

        self.assertIn("ORDER BY", result["sql"])

    def test_generate_sql_query_adds_target_metric_constraint(self):
        from app.core.llm import generate_sql_query

        datasource = SimpleNamespace(
            source_type="postgres",
            metadata_prompt="metadata",
            metrics_prompt="可用指标：\n- 总产出: 计算公式：SUM(output_qty)\n- 良率: 计算公式：SUM(good_qty) / SUM(output_qty)",
            text2sql_prompt="base",
        )
        metric_match = {
            "name": "良率",
            "formula": "SUM(good_qty) / SUM(output_qty)",
        }

        async def fake_chat_completion(messages, temperature=0.2, config_override=None):
            system_prompt = messages[0]["content"]
            self.assertIn("本次问题命中的目标指标：良率", system_prompt)
            self.assertIn("必须使用以下指标公式", system_prompt)
            self.assertIn("SUM(good_qty) / SUM(output_qty)", system_prompt)
            self.assertNotIn("总产出", system_prompt)
            return "SELECT SUM(good_qty) / SUM(output_qty) AS 良率 FROM prod"

        with patch("app.core.llm.chat_completion", new=fake_chat_completion):
            result = asyncio.run(
                generate_sql_query("查询良率", datasource=datasource, metric_match=metric_match)
            )

        self.assertIn("SUM(good_qty) / SUM(output_qty)", result["sql"])


if __name__ == "__main__":
    unittest.main()
