import os
import tempfile
import unittest

import pandas as pd


class SqlGuardTests(unittest.TestCase):
    def _build_excel(self) -> str:
        fd, path = tempfile.mkstemp(suffix=".xlsx")
        os.close(fd)

        ngtype = pd.DataFrame(
            [
                {
                    "MAINID": "m1",
                    "NGTYPE": "1001/OP100 - Failed Hall Cal test",
                    "STN": "OP100A",
                    "NGCOUNT": 136,
                },
                {
                    "MAINID": "m1",
                    "NGTYPE": "1001/OP100 - Failed Hall Cal test",
                    "STN": "OP100C",
                    "NGCOUNT": 85,
                },
            ]
        )
        rtyinfo = pd.DataFrame(
            [
                {"MAINID": "m2", "STN": "OP100A"},
                {"MAINID": "m3", "STN": "OP100B"},
            ]
        )

        with pd.ExcelWriter(path) as writer:
            ngtype.to_excel(writer, sheet_name="IP_PA_NGTYPE-失效详情", index=False)
            rtyinfo.to_excel(writer, sheet_name="IP_PA_RTYINFO-各工站投入产出详情", index=False)

        return path

    def test_detect_excel_join_risk_when_join_keys_have_no_overlap(self):
        from app.core.sql_guard import detect_excel_join_risk

        path = self._build_excel()
        try:
            sql = """
            SELECT t2.STN, COUNT(*) AS occurrence_count
            FROM ngtype t1
            JOIN rtyinfo t2 ON t1.MAINID = t2.MAINID
            WHERE t1.NGTYPE = '1001/OP100 - Failed Hall Cal test'
            GROUP BY t2.STN
            """

            risk = detect_excel_join_risk(path, sql)

            self.assertIsNotNone(risk)
            self.assertIn("没有可匹配的取值", risk["message"])
            self.assertIn("不要使用 ngtype.MAINID = rtyinfo.MAINID", risk["hint"])
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_detect_excel_join_risk_returns_none_for_single_table_query(self):
        from app.core.sql_guard import detect_excel_join_risk

        path = self._build_excel()
        try:
            sql = """
            SELECT STN, SUM(NGCOUNT) AS total_ng_count
            FROM ngtype
            WHERE NGTYPE = '1001/OP100 - Failed Hall Cal test'
            GROUP BY STN
            """

            risk = detect_excel_join_risk(path, sql)

            self.assertIsNone(risk)
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_detect_excel_join_risk_does_not_flag_join_keys_used_only_in_on_clause(self):
        from app.core.sql_guard import detect_excel_join_risk

        path = self._build_excel()
        try:
            mainrecord = pd.DataFrame([{"ID": "m1", "LINE": "L1"}])
            production = pd.DataFrame([{"MAINID": "m1", "PARTNO": "P1"}])
            with pd.ExcelWriter(path, mode="a", engine="openpyxl", if_sheet_exists="replace") as writer:
                mainrecord.to_excel(writer, sheet_name="IP_PA_MAINRECORD-班次主数据", index=False)
                production.to_excel(writer, sheet_name="IP_PA_PRODUCTION-各型号产出", index=False)

            sql = """
            SELECT p.PARTNO, SUM(n.NGCOUNT) AS total_ng_count
            FROM ngtype n
            JOIN mainrecord m ON n.MAINID = m.ID
            JOIN production p ON m.ID = p.MAINID
            WHERE n.STN = 'OP100A'
              AND n.NGTYPE = '1001/OP100 - Failed Hall Cal test'
            GROUP BY p.PARTNO
            ORDER BY total_ng_count DESC
            """

            risk = detect_excel_join_risk(path, sql)

            self.assertIsNone(risk)
        finally:
            if os.path.exists(path):
                os.remove(path)


if __name__ == "__main__":
    unittest.main()
