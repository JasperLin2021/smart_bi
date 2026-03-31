import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


class LlmDetailPromptTests(unittest.TestCase):
    def test_generate_sql_query_adds_detail_guidance_for_detail_question(self):
        from app.core.llm import generate_sql_query

        datasource = SimpleNamespace(
            source_type="excel",
            metadata_prompt="数据库表结构信息：- ngtype 表：失效详情",
            metrics_prompt="",
            text2sql_prompt="你是SQL专家",
        )

        async def fake_chat_completion(messages, temperature=0.2, config_override=None):
            system_prompt = messages[0]["content"]
            self.assertIn("如果用户明确要求详细记录", system_prompt)
            self.assertIn("优先选择最贴近业务事件的明细表", system_prompt)
            return "SELECT * FROM ngtype"

        with patch("app.core.llm.chat_completion", new=fake_chat_completion):
            result = asyncio.run(
                generate_sql_query(
                    "列出OP100A工位上所有属于'1001/OP100 - Failed Hall Cal test'不良类型的详细记录。",
                    datasource=datasource,
                )
            )

        self.assertEqual(result["sql"], "SELECT * FROM ngtype")


if __name__ == "__main__":
    unittest.main()
