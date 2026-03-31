import unittest


class DrillHistoryPayloadTests(unittest.TestCase):
    def test_query_ask_request_accepts_drill_context(self):
        from app.schemas.query import QueryAskRequest

        payload = QueryAskRequest.model_validate(
            {
                "question": "只看产线为 REPS3 BSI 的数据，按异常类型继续分析。",
                "mode": "text2sql",
                "datasource_id": 2,
                "drill_context": {
                    "pathLabel": "看不良类型分布",
                    "sourceLabel": "产线",
                    "sourceValue": "REPS3 BSI",
                    "targetLabel": "异常类型",
                },
            }
        )

        self.assertEqual(payload.drill_context["sourceLabel"], "产线")
        self.assertEqual(payload.drill_context["targetLabel"], "异常类型")


if __name__ == "__main__":
    unittest.main()
