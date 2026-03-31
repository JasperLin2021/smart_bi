import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


class QuerySqlGuardTests(unittest.TestCase):
    def test_generate_safe_sql_retries_when_excel_join_is_risky(self):
        from app.api.query import _generate_safe_sql

        datasource = SimpleNamespace(
            source_type="excel",
            database_url="/tmp/fake.xlsx",
        )

        first_sql = "SELECT t2.STN FROM ngtype t1 JOIN rtyinfo t2 ON t1.MAINID = t2.MAINID"
        second_sql = "SELECT STN FROM ngtype"

        with patch(
            "app.api.query.generate_sql_query",
            new=AsyncMock(side_effect=[{"sql": first_sql}, {"sql": second_sql}]),
        ) as mocked_generate, patch(
            "app.api.query.detect_excel_join_risk",
            side_effect=[
                {"message": "bad join", "hint": "use single table"},
                None,
            ],
        ):
            sql = asyncio.run(_generate_safe_sql("q", datasource))

        self.assertEqual(sql, second_sql)
        self.assertEqual(mocked_generate.await_count, 2)

    def test_generate_safe_sql_raises_when_retry_is_still_risky(self):
        from app.api.query import _generate_safe_sql

        datasource = SimpleNamespace(
            source_type="excel",
            database_url="/tmp/fake.xlsx",
        )

        with patch(
            "app.api.query.generate_sql_query",
            new=AsyncMock(side_effect=[{"sql": "select 1"}, {"sql": "select 2"}]),
        ), patch(
            "app.api.query.detect_excel_join_risk",
            side_effect=[
                {"message": "bad join", "hint": "retry"},
                {"message": "still bad", "hint": "retry again"},
            ],
        ):
            with self.assertRaises(ValueError) as ctx:
                asyncio.run(_generate_safe_sql("q", datasource))

        self.assertIn("高风险JOIN", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
