import unittest
from types import SimpleNamespace
from unittest.mock import patch


class QueryHistoryModelTests(unittest.TestCase):
    def test_get_history_detail_returns_stored_llm_model(self):
        with patch.dict("sys.modules", {"duckdb": SimpleNamespace(), "pandas": SimpleNamespace()}):
            from app.api.query import get_history_detail

            history = SimpleNamespace(
                id=7,
                user_id=1,
                datasource_id=3,
                question="[SQL] 查询测试",
                sql_query="select 1",
                result_json='{"columns":["a"],"rows":[{"a":1}]}',
                summary="ok",
                llm_model="gemini-2.5-flash-lite",
                mode="text2sql",
                drill_context=None,
                parent_history_id=None,
                created_at=SimpleNamespace(strftime=lambda _fmt: "2026-04-02 10:00"),
            )

            class FakeQuery:
                def __init__(self, row):
                    self.row = row

                def filter(self, *_args, **_kwargs):
                    return self

                def order_by(self, *_args, **_kwargs):
                    return self

                def first(self):
                    return self.row

                def all(self):
                    return [self.row]

            class FakeDb:
                def query(self, _model):
                    return FakeQuery(history)

            current_user = SimpleNamespace(id=1)
            result = get_history_detail(7, db=FakeDb(), current_user=current_user)

        self.assertEqual(result["llm_model"], "gemini-2.5-flash-lite")


if __name__ == "__main__":
    unittest.main()
