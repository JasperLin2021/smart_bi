import asyncio
import unittest
from unittest.mock import AsyncMock, patch


class DrillSuggesterTests(unittest.TestCase):
    def test_suggest_drill_actions_maps_optional_detail_action(self):
        from app.core.drill_suggester import suggest_drill_actions

        raw = """
        {
          "actions": [],
          "detail_action": {
            "label": "查看明细",
            "question": "在当前筛选条件下查看详细记录信息。"
          }
        }
        """

        with patch("app.core.drill_suggester.chat_completion", new=AsyncMock(return_value=raw)):
            result = asyncio.run(
                suggest_drill_actions(
                    question="今天各工站不良数量分布",
                    sql_query="select stn, sum(ngcount) as total_ng_count from ngtype group by stn",
                    columns=["STN", "total_ng_count"],
                    row={"STN": "OP100A", "total_ng_count": 136},
                    selected_column="STN",
                )
            )

        self.assertEqual(result["actions"], [])
        self.assertIsNotNone(result["detail_action"])
        self.assertEqual(result["detail_action"]["action"], "show_rows")
        self.assertEqual(result["detail_action"]["label"], "查看明细")

    def test_suggest_drill_actions_prompt_prefers_business_meaningful_metrics(self):
        from app.core.drill_suggester import suggest_drill_actions

        async def fake_chat_completion(messages, temperature=0.1):
            system_prompt = messages[0]["content"]
            self.assertIn("优先选择更有业务意义的聚合口径", system_prompt)
            self.assertIn("不要默认使用 COUNT(*)", system_prompt)
            return '{"actions":[]}'

        with patch("app.core.drill_suggester.chat_completion", new=fake_chat_completion):
            actions = asyncio.run(
                suggest_drill_actions(
                    question="某不良项在不同工站上的分布",
                    sql_query="select stn, count(*) as occurrence_frequency from ngtype group by stn",
                    columns=["STN", "occurrence_frequency"],
                    row={"STN": "OP100A", "occurrence_frequency": 1},
                    selected_column="STN",
                )
            )

        self.assertEqual(actions["actions"], [])
        self.assertIsNone(actions["detail_action"])

    def test_suggest_drill_actions_maps_llm_json_to_actions(self):
        from app.core.drill_suggester import suggest_drill_actions

        raw = """
        {
          "actions": [
            {
              "id": "line_to_ngtype",
              "label": "看不良类型分布",
              "target_label": "NGTYPE",
              "question": "只看当前产线，按 NGTYPE 继续分析。"
            }
          ]
        }
        """

        with patch("app.core.drill_suggester.chat_completion", new=AsyncMock(return_value=raw)):
            actions = asyncio.run(
                suggest_drill_actions(
                    question="最近一个月各产线的不良数量分布",
                    sql_query="select line, sum(ngcount) as total from ngtype group by line",
                    columns=["LINE", "total"],
                    row={"LINE": "L01", "total": 12},
                    selected_column="LINE",
                )
            )

        self.assertEqual(len(actions["actions"]), 1)
        self.assertEqual(actions["actions"][0]["label"], "看不良类型分布")
        self.assertEqual(actions["actions"][0]["source_column"], "LINE")
        self.assertEqual(actions["actions"][0]["source_value"], "L01")
        self.assertEqual(actions["actions"][0]["target_column"], "NGTYPE")
        self.assertIsNone(actions["detail_action"])

    def test_suggest_drill_actions_returns_empty_when_llm_fails(self):
        from app.core.drill_suggester import suggest_drill_actions

        with patch("app.core.drill_suggester.chat_completion", new=AsyncMock(side_effect=RuntimeError("boom"))):
            actions = asyncio.run(
                suggest_drill_actions(
                    question="q",
                    sql_query="select 1",
                    columns=["LINE"],
                    row={"LINE": "L01"},
                    selected_column="LINE",
                )
            )

        self.assertEqual(actions["actions"], [])
        self.assertIsNone(actions["detail_action"])


if __name__ == "__main__":
    unittest.main()
