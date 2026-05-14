import unittest


class MetricPromptSyncTests(unittest.TestCase):
    def test_build_metrics_prompt_lists_active_metrics(self):
        from app.core.metric_prompt_sync import build_metrics_prompt

        prompt = build_metrics_prompt(
            [
                {
                    "name": "OEE",
                    "description": "设备综合效率",
                    "definition": "OEE = 时间开动率 × 性能效率 × 良品率",
                    "formula": "AVG(mainrecord.OEE)",
                    "calculation_config": {
                        "statistical_window": "自然日",
                        "time_grain": "day",
                        "filters": [
                            {"field": "factory", "operator": "=", "value": "A厂"}
                        ],
                        "null_handling": "停机时间为空按 0 处理",
                        "dedup_key": "machine_id + shift_date",
                    },
                },
                {
                    "name": "产出",
                    "description": "",
                    "definition": "在实际生产中，最终做出来了多少",
                    "formula": "SUM(production.OKCOUNT)",
                },
            ]
        )

        self.assertIn("可用指标：", prompt)
        self.assertIn("OEE", prompt)
        self.assertIn("AVG(mainrecord.OEE)", prompt)
        self.assertIn("统计周期：自然日", prompt)
        self.assertIn("时间粒度：day", prompt)
        self.assertIn("过滤条件：factory = A厂", prompt)
        self.assertIn("空值处理：停机时间为空按 0 处理", prompt)
        self.assertIn("去重键：machine_id + shift_date", prompt)
        self.assertIn("产出", prompt)

    def test_build_metrics_prompt_returns_none_for_empty_metrics(self):
        from app.core.metric_prompt_sync import build_metrics_prompt

        self.assertIsNone(build_metrics_prompt([]))


if __name__ == "__main__":
    unittest.main()
