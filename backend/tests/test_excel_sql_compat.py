import unittest


class ExcelSqlCompatTests(unittest.TestCase):
    def test_rewrite_sqlite_now_minus_one_month_for_duckdb(self):
        from app.core.excel_executor import rewrite_excel_sql_for_duckdb

        sql = "SELECT * FROM ngtype WHERE DATE(sumdatetime) >= DATE('now', '-1 month')"
        rewritten = rewrite_excel_sql_for_duckdb(sql)

        self.assertIn("CURRENT_DATE - INTERVAL '1 month'", rewritten)
        self.assertNotIn("DATE('now', '-1 month')", rewritten)

    def test_rewrite_sqlite_date_modifier_on_column_to_interval_expression(self):
        from app.core.excel_executor import rewrite_excel_sql_for_duckdb

        sql = "SELECT DATE(sumdatetime, '-1 day') AS prev_day FROM ngtype"
        rewritten = rewrite_excel_sql_for_duckdb(sql)

        self.assertIn("CAST(sumdatetime AS DATE) - INTERVAL '1 day'", rewritten)
        self.assertNotIn("DATE(sumdatetime, '-1 day')", rewritten)


if __name__ == "__main__":
    unittest.main()
