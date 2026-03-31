import asyncio
import unittest


class QuerySummaryGuardTests(unittest.TestCase):
    def test_non_empty_result_does_not_return_no_data_summary(self):
        from app.api.query import _normalize_summary

        result = {
            "columns": ["ID", "STN"],
            "rows": [{"ID": "1", "STN": "OP100A"}],
        }
        summary = "未找到符合条件的详细记录。"

        normalized = _normalize_summary("列出OP100A工位详细记录", result, summary)

        self.assertIn("查询返回 1 条记录", normalized)
        self.assertNotIn("未找到", normalized)

    def test_empty_result_keeps_no_data_summary(self):
        from app.api.query import _normalize_summary

        result = {"columns": ["ID"], "rows": []}
        summary = "未找到符合条件的详细记录。"

        normalized = _normalize_summary("列出明细", result, summary)

        self.assertEqual(normalized, summary)


if __name__ == "__main__":
    unittest.main()
