import asyncio
import inspect
import json
import unittest
from unittest.mock import AsyncMock, patch


class SummaryGenerationTests(unittest.TestCase):
    def test_generate_summary_uses_chart_data_prompt_when_chart_spec_is_available(self):
        from app.core.llm import generate_summary

        result = {
            "columns": ["ALARMID", "EQUIPMENTID", "trend_date", "occurrence_count"],
            "rows": [
                {"ALARMID": "A01", "EQUIPMENTID": "EQ-1", "trend_date": "2026-05-01", "occurrence_count": 12},
                {"ALARMID": "A01", "EQUIPMENTID": "EQ-1", "trend_date": "2026-05-02", "occurrence_count": 18},
            ],
        }
        chart_spec = {
            "chart_type": "line",
            "x_field": "trend_date",
            "y_field": "occurrence_count",
            "series_fields": ["EQUIPMENTID"],
            "facet_field": "ALARMID",
        }

        with patch("app.core.llm.chat_completion", new=AsyncMock(return_value="A01 下 EQ-1 呈上升趋势。")) as mocked:
            summary = asyncio.run(
                generate_summary(
                    "TOP3的 alarmcode中发生次数最多的设备的趋势图 也取 TOP10",
                    result,
                    chart_spec=chart_spec,
                )
            )

        self.assertEqual(summary, "A01 下 EQ-1 呈上升趋势。")
        messages = mocked.await_args.args[0]
        system_prompt = messages[0]["content"]
        user_prompt = messages[1]["content"]

        self.assertIn("图表数据", system_prompt)
        self.assertIn("原始问题", system_prompt)
        self.assertIn("先理解原始问题", system_prompt)
        self.assertIn("像分析图表的人一样", system_prompt)
        self.assertIn("不要只复述字段", system_prompt)
        self.assertIn("不要使用固定模板", system_prompt)

        payload = json.loads(user_prompt.split("图表上下文:", 1)[1])
        self.assertEqual(payload["original_question"], "TOP3的 alarmcode中发生次数最多的设备的趋势图 也取 TOP10")
        self.assertEqual(payload["chart_spec"]["chart_type"], "line")
        self.assertEqual(payload["chart_data"]["row_count"], 2)
        self.assertEqual(payload["chart_data"]["rows"][0]["occurrence_count"], 12)

    def test_chart_summary_samples_each_facet_value_instead_of_only_first_rows(self):
        from app.core.llm import generate_summary

        rows = []
        alarm_specs = [("A01", 10, 10), ("A02", 2, 10), ("A03", 3, 10)]
        for alarm_id, equipment_count, day_count in alarm_specs:
            for equipment_index in range(equipment_count):
                for day_index in range(day_count):
                    rows.append(
                        {
                            "ALARMID": alarm_id,
                            "EQUIPMENTID": f"EQ-{equipment_index + 1}",
                            "trend_date": f"2026-05-{day_index + 1:02d}",
                            "occurrence_count": 10 + day_index,
                        }
                    )
        result = {
            "columns": ["ALARMID", "EQUIPMENTID", "trend_date", "occurrence_count"],
            "rows": rows,
        }
        chart_spec = {
            "chart_type": "line",
            "x_field": "trend_date",
            "y_field": "occurrence_count",
            "series_fields": ["EQUIPMENTID"],
            "facet_field": "ALARMID",
        }

        with patch("app.core.llm.chat_completion", new=AsyncMock(return_value="覆盖三个报警码。")) as mocked:
            asyncio.run(
                generate_summary(
                    "TOP3的 alarmcode中发生次数最多的设备的趋势图 也取 TOP10",
                    result,
                    chart_spec=chart_spec,
                )
            )

        messages = mocked.await_args.args[0]
        payload = json.loads(messages[1]["content"].split("图表上下文:", 1)[1])
        sampled_alarm_ids = {row["ALARMID"] for row in payload["chart_data"]["rows"]}
        alarm_coverage = next(
            item for item in payload["chart_data"]["field_coverage"] if item["field"] == "ALARMID"
        )

        self.assertLessEqual(len(payload["chart_data"]["rows"]), 120)
        self.assertEqual(sampled_alarm_ids, {"A01", "A02", "A03"})
        self.assertEqual(alarm_coverage["distinct_count"], 3)
        self.assertEqual(alarm_coverage["values"], ["A01", "A02", "A03"])

    def test_agentic_query_passes_chart_spec_to_summary_generation(self):
        import app.api.query as query_api

        source = inspect.getsource(query_api)

        self.assertIn("generate_summary(question, result, chart_spec=chart_spec)", source)


if __name__ == "__main__":
    unittest.main()
