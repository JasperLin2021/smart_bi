import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch


class LlmQueryPlanPromptTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
