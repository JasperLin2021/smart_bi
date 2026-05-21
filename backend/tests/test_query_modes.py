import unittest
import asyncio
from types import SimpleNamespace
from unittest.mock import patch

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

    def test_agentic_empty_result_confirmation_helper_is_removed(self):
        import app.api.query as query_api

        self.assertFalse(hasattr(query_api, "_agentic_empty_result_confirmation"))
        self.assertFalse(hasattr(query_api, "_agentic_empty_result_trace"))

    def test_agentic_empty_result_builds_non_blocking_diagnostics(self):
        from app.api.query import _build_agentic_empty_diagnostics

        diagnostics = _build_agentic_empty_diagnostics(
            "查看最近30天报警趋势",
            "SELECT day, COUNT(*) AS cnt FROM alarms WHERE day >= CURRENT_DATE - INTERVAL '30 days' GROUP BY day",
            {"columns": ["day", "cnt"], "rows": []},
        )

        self.assertEqual(diagnostics["reason"], "no_matching_rows")
        self.assertIn("SQL 执行成功但返回 0 行", diagnostics["checks"])
        self.assertGreaterEqual(len(diagnostics["suggested_actions"]), 3)
        self.assertTrue(all("question" in item for item in diagnostics["suggested_actions"]))

    def test_agentic_value_probe_extracts_short_code_without_field_words(self):
        from app.api.query import _extract_agentic_value_probe_terms

        terms = _extract_agentic_value_probe_terms("SS的step中，top10的alarm_id的次数趋势图")

        self.assertEqual(terms, ["SS"])

    def test_agentic_value_probe_context_prefers_matched_column(self):
        from app.api.query import _format_agentic_value_probe_context

        context = _format_agentic_value_probe_context(
            {
                "terms": ["SS"],
                "matches": [
                    {
                        "term": "SS",
                        "table": "sheet1",
                        "column": "STEP",
                        "matched_value": "SS",
                        "match_count": 12,
                        "sample_rows": [{"STEP": "SS", "ALARMID": "A01"}],
                    }
                ],
            }
        )

        self.assertIn("sheet1.STEP", context)
        self.assertIn("SS", context)
        self.assertIn("优先把这些片段理解为字段值过滤条件", context)

    def test_agentic_value_probe_executes_lightweight_scan_and_emits_trace(self):
        from app.api.query import _append_agentic_value_probe

        datasource = SimpleNamespace(
            source_type="excel",
            metadata_prompt="sheet1(STEP, ALARMID, SUMDATETIME)",
            schema_metadata=None,
            database_url="/tmp/alarm.xlsx",
        )
        trace = []

        def fake_execute(_datasource, sql):
            if '"STEP"' in sql and "COUNT(*)" in sql:
                return (
                    {"columns": ["matched_value", "match_count"]},
                    [{"matched_value": "SS", "match_count": 12}],
                )
            if '"STEP"' in sql and "SELECT *" in sql:
                return (
                    {"columns": ["STEP", "ALARMID"]},
                    [{"STEP": "SS", "ALARMID": "A01"}],
                )
            return ({"columns": [], "rows": []}, [])

        with patch("app.api.query._execute_datasource_sql", side_effect=fake_execute):
            probe, context = asyncio.run(
                _append_agentic_value_probe(
                    datasource,
                    "SS的step中，top10的alarm_id的次数趋势图",
                    trace,
                )
            )

        self.assertEqual(probe["matches"][0]["column"], "STEP")
        self.assertIn("sheet1.STEP", context)
        self.assertEqual(trace[0]["stage"], "value_probe")
        self.assertEqual(trace[0]["status"], "success")


if __name__ == "__main__":
    unittest.main()
