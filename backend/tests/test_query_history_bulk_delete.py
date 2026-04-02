import unittest
from types import SimpleNamespace
from unittest.mock import patch


class QueryHistoryBulkDeleteTests(unittest.TestCase):
    def test_delete_all_history_removes_only_current_user_records_in_scope(self):
        with patch.dict("sys.modules", {"duckdb": SimpleNamespace(), "pandas": SimpleNamespace()}):
            from app.api.query import delete_all_history
            from app.models.query import QueryHistory

            deleted_rows = []

            class FakeDeleteQuery:
                def __init__(self):
                    self.filters = []

                def filter(self, *args, **_kwargs):
                    self.filters.extend(args)
                    return self

                def delete(self, synchronize_session=False):
                    self.synchronize_session = synchronize_session
                    return 3

            class FakeDb:
                def query(self, model):
                    if model is not QueryHistory:
                        raise AssertionError(f"unexpected model: {model}")
                    return FakeDeleteQuery()

                def commit(self):
                    deleted_rows.append("committed")

            result = delete_all_history(
                datasource_id=8,
                db=FakeDb(),
                current_user=SimpleNamespace(id=10),
            )

        self.assertEqual(result["deleted"], 3)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(deleted_rows, ["committed"])


if __name__ == "__main__":
    unittest.main()
