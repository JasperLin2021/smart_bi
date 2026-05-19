import unittest
from types import SimpleNamespace

from fastapi import HTTPException


class QueryModePermissionTests(unittest.TestCase):
    def test_query_mode_normalization_maps_legacy_explore_to_agentic(self):
        from app.api.query import _normalize_query_mode

        self.assertEqual(_normalize_query_mode("business", dataset_id=1), "business")
        self.assertEqual(_normalize_query_mode("explore", dataset_id=None), "agentic")
        self.assertEqual(_normalize_query_mode("explore", dataset_id=1), "agentic")
        self.assertEqual(_normalize_query_mode("agentic", dataset_id=None), "agentic")
        self.assertEqual(_normalize_query_mode("text2sql", dataset_id=1), "business")
        self.assertEqual(_normalize_query_mode("text2sql", dataset_id=None), "agentic")

        with self.assertRaises(HTTPException) as ctx:
            _normalize_query_mode("chat", dataset_id=None)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_history_mode_normalization_maps_legacy_explore_to_agentic(self):
        from app.api.query import _normalize_history_mode

        self.assertEqual(_normalize_history_mode("business"), "business")
        self.assertEqual(_normalize_history_mode("agentic"), "agentic")
        self.assertEqual(_normalize_history_mode("explore"), "agentic")

    def test_business_mode_requires_dataset_and_agentic_requires_admin_role(self):
        from app.api.query import _ensure_query_mode_allowed

        with self.assertRaises(HTTPException) as missing_dataset:
            _ensure_query_mode_allowed(
                "business",
                dataset_id=None,
                current_user=SimpleNamespace(role="user"),
            )
        self.assertEqual(missing_dataset.exception.status_code, 400)

        with self.assertRaises(HTTPException) as denied:
            _ensure_query_mode_allowed(
                "agentic",
                dataset_id=None,
                current_user=SimpleNamespace(role="user"),
            )
        self.assertEqual(denied.exception.status_code, 403)

        for role in ("dept_admin", "org_admin", "super_admin"):
            _ensure_query_mode_allowed(
                "agentic",
                dataset_id=None,
                current_user=SimpleNamespace(role=role),
            )

    def test_agentic_mode_rejects_dataset_scope_even_for_admins(self):
        from app.api.query import _ensure_query_mode_allowed

        with self.assertRaises(HTTPException) as ctx:
            _ensure_query_mode_allowed(
                "agentic",
                dataset_id=1,
                current_user=SimpleNamespace(role="org_admin"),
            )
        self.assertEqual(ctx.exception.status_code, 400)

    def test_agentic_mode_is_datasource_only_and_admin_gated(self):
        from app.api.query import _ensure_query_mode_allowed

        with self.assertRaises(HTTPException) as dataset_scope:
            _ensure_query_mode_allowed(
                "agentic",
                dataset_id=1,
                current_user=SimpleNamespace(role="org_admin"),
            )
        self.assertEqual(dataset_scope.exception.status_code, 400)

        with self.assertRaises(HTTPException) as denied:
            _ensure_query_mode_allowed(
                "agentic",
                dataset_id=None,
                current_user=SimpleNamespace(role="user"),
            )
        self.assertEqual(denied.exception.status_code, 403)

        for role in ("dept_admin", "department_admin", "org_admin", "super_admin"):
            _ensure_query_mode_allowed(
                "agentic",
                dataset_id=None,
                current_user=SimpleNamespace(role=role),
            )

    def test_agentic_empty_result_summary_asks_user_to_confirm_filters(self):
        from app.api.query import _agentic_empty_result_confirmation

        summary = _agentic_empty_result_confirmation(
            "最近30天报警趋势",
            {"columns": ["trend_date", "alarm_count"], "rows": []},
            "SELECT trend_date, COUNT(*) AS alarm_count FROM alarms WHERE trend_date >= CURRENT_DATE - 30",
        )

        self.assertIn("没有返回数据", summary)
        self.assertIn("请确认", summary)
        self.assertIn("时间范围", summary)
        self.assertIn("筛选条件", summary)


if __name__ == "__main__":
    unittest.main()
