import unittest
from types import SimpleNamespace

from fastapi import HTTPException


class QueryModePermissionTests(unittest.TestCase):
    def test_query_mode_normalization_replaces_text2sql_and_rejects_chat(self):
        from app.api.query import _normalize_query_mode

        self.assertEqual(_normalize_query_mode("business", dataset_id=1), "business")
        self.assertEqual(_normalize_query_mode("explore", dataset_id=None), "explore")
        self.assertEqual(_normalize_query_mode("text2sql", dataset_id=1), "business")
        self.assertEqual(_normalize_query_mode("text2sql", dataset_id=None), "explore")

        with self.assertRaises(HTTPException) as ctx:
            _normalize_query_mode("chat", dataset_id=None)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_business_mode_requires_dataset_and_explore_requires_admin_role(self):
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
                "explore",
                dataset_id=None,
                current_user=SimpleNamespace(role="user"),
            )
        self.assertEqual(denied.exception.status_code, 403)

        for role in ("dept_admin", "org_admin", "super_admin"):
            _ensure_query_mode_allowed(
                "explore",
                dataset_id=None,
                current_user=SimpleNamespace(role=role),
            )


if __name__ == "__main__":
    unittest.main()
