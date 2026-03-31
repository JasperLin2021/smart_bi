import unittest


class QueryHistoryLinkageTests(unittest.TestCase):
    def test_query_ask_request_supports_parent_history_id(self):
        from app.schemas.query import QueryAskRequest

        payload = QueryAskRequest(question="q", parent_history_id=12)
        self.assertEqual(payload.parent_history_id, 12)


if __name__ == "__main__":
    unittest.main()
