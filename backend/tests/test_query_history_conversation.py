import os
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class QueryHistoryConversationTests(unittest.TestCase):
    def _db(self):
        from app.db.base_class import Base
        from app.models.organization import Organization  # noqa: F401
        from app.models.query import QueryHistory

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine, tables=[QueryHistory.__table__])
        db = sessionmaker(bind=engine)()
        self.addCleanup(engine.dispose)
        self.addCleanup(db.close)
        return db

    def test_history_list_groups_followups_under_conversation_root(self):
        with (
            patch.dict(os.environ, {"DATABASE_URL": "sqlite:///:memory:"}),
            patch.dict("sys.modules", {"duckdb": SimpleNamespace(), "pandas": SimpleNamespace()}),
        ):
            from app.api.query import history
            from app.models.query import QueryHistory

            db = self._db()
            base = datetime(2026, 5, 19, 10, 0)
            root = QueryHistory(
                id=1,
                user_id=7,
                datasource_id=3,
                question="[探索模式] 看最近30天报警趋势",
                created_at=base,
            )
            followup = QueryHistory(
                id=2,
                user_id=7,
                datasource_id=3,
                parent_history_id=1,
                question="[探索模式] 按设备展开",
                created_at=base + timedelta(minutes=5),
            )
            separate = QueryHistory(
                id=3,
                user_id=7,
                datasource_id=3,
                question="[探索模式] 查看良率",
                created_at=base + timedelta(minutes=10),
            )
            db.add_all([root, followup, separate])
            db.commit()

            result = history(datasource_id=3, db=db, current_user=SimpleNamespace(id=7))

        self.assertEqual([item["id"] for item in result["items"]], [3, 1])
        self.assertEqual(result["items"][1]["question"], "[探索模式] 看最近30天报警趋势")
        self.assertEqual(result["items"][1]["created_at"], "2026-05-19 10:05")

    def test_history_list_filters_by_query_mode(self):
        with (
            patch.dict(os.environ, {"DATABASE_URL": "sqlite:///:memory:"}),
            patch.dict("sys.modules", {"duckdb": SimpleNamespace(), "pandas": SimpleNamespace()}),
        ):
            from app.api.query import history
            from app.models.query import QueryHistory

            db = self._db()
            base = datetime(2026, 5, 19, 10, 0)
            db.add_all(
                [
                    QueryHistory(
                        id=1,
                        user_id=7,
                        datasource_id=3,
                        question="[业务问数] 看销售额",
                        mode="business",
                        created_at=base,
                    ),
                    QueryHistory(
                        id=2,
                        user_id=7,
                        datasource_id=3,
                        question="[探索模式] 看报警趋势",
                        mode="agentic",
                        created_at=base + timedelta(minutes=1),
                    ),
                    QueryHistory(
                        id=3,
                        user_id=7,
                        datasource_id=3,
                        question="[探索问数] 旧探索历史",
                        mode="explore",
                        created_at=base + timedelta(minutes=2),
                    ),
                    QueryHistory(
                        id=4,
                        user_id=7,
                        datasource_id=3,
                        question="[业务问数] 旧业务历史",
                        mode=None,
                        created_at=base + timedelta(minutes=3),
                    ),
                ]
            )
            db.commit()

            business = history(datasource_id=3, mode="business", db=db, current_user=SimpleNamespace(id=7))
            agentic = history(datasource_id=3, mode="agentic", db=db, current_user=SimpleNamespace(id=7))

        self.assertEqual([item["id"] for item in business["items"]], [4, 1])
        self.assertEqual([item["mode"] for item in business["items"]], ["business", "business"])
        self.assertEqual([item["id"] for item in agentic["items"]], [3, 2])
        self.assertEqual([item["mode"] for item in agentic["items"]], ["agentic", "agentic"])

    def test_history_detail_returns_conversation_turns_for_root(self):
        with (
            patch.dict(os.environ, {"DATABASE_URL": "sqlite:///:memory:"}),
            patch.dict("sys.modules", {"duckdb": SimpleNamespace(), "pandas": SimpleNamespace()}),
        ):
            from app.api.query import get_history_detail
            from app.models.query import QueryHistory

            db = self._db()
            base = datetime(2026, 5, 19, 10, 0)
            db.add_all(
                [
                    QueryHistory(
                        id=1,
                        user_id=7,
                        datasource_id=3,
                        question="[探索模式] 看最近30天报警趋势",
                        summary="趋势完成",
                        result_json='{"columns":["day"],"rows":[{"day":"2026-05-19"}]}',
                        created_at=base,
                        mode="agentic",
                        llm_model="test-model",
                    ),
                    QueryHistory(
                        id=2,
                        user_id=7,
                        datasource_id=3,
                        parent_history_id=1,
                        question="[探索模式] 按设备展开",
                        summary="设备完成",
                        result_json='{"columns":["equipment"],"rows":[{"equipment":"EQ1"}]}',
                        created_at=base + timedelta(minutes=5),
                        mode="agentic",
                        llm_model="test-model",
                    ),
                ]
            )
            db.commit()

            result = get_history_detail(1, db=db, current_user=SimpleNamespace(id=7))

        self.assertEqual([turn["id"] for turn in result["conversation"]], [1, 2])
        self.assertEqual(result["conversation"][1]["summary"], "设备完成")
        self.assertEqual(result["conversation"][1]["result"]["rows"], [{"equipment": "EQ1"}])

    def test_delete_history_root_removes_conversation_followups(self):
        with (
            patch.dict(os.environ, {"DATABASE_URL": "sqlite:///:memory:"}),
            patch.dict("sys.modules", {"duckdb": SimpleNamespace(), "pandas": SimpleNamespace()}),
        ):
            from app.api.query import delete_history
            from app.models.query import QueryHistory

            db = self._db()
            base = datetime(2026, 5, 19, 10, 0)
            db.add_all(
                [
                    QueryHistory(id=1, user_id=7, datasource_id=3, question="根问题", created_at=base),
                    QueryHistory(
                        id=2,
                        user_id=7,
                        datasource_id=3,
                        parent_history_id=1,
                        question="追问",
                        created_at=base + timedelta(minutes=1),
                    ),
                    QueryHistory(id=3, user_id=7, datasource_id=3, question="另一个对话", created_at=base),
                ]
            )
            db.commit()

            result = delete_history(1, db=db, current_user=SimpleNamespace(id=7))
            remaining_ids = [row.id for row in db.query(QueryHistory).order_by(QueryHistory.id).all()]

        self.assertEqual(result, {"status": "ok"})
        self.assertEqual(remaining_ids, [3])

    def test_parent_history_id_is_normalized_to_same_scope_root(self):
        with (
            patch.dict(os.environ, {"DATABASE_URL": "sqlite:///:memory:"}),
            patch.dict("sys.modules", {"duckdb": SimpleNamespace(), "pandas": SimpleNamespace()}),
        ):
            from app.api.query import _resolve_parent_history_id
            from app.models.query import QueryHistory

            db = self._db()
            base = datetime(2026, 5, 19, 10, 0)
            db.add_all(
                [
                    QueryHistory(
                        id=1,
                        user_id=7,
                        datasource_id=3,
                        question="根问题",
                        mode="agentic",
                        created_at=base,
                    ),
                    QueryHistory(
                        id=2,
                        user_id=7,
                        datasource_id=3,
                        parent_history_id=1,
                        question="追问",
                        mode="agentic",
                        created_at=base + timedelta(minutes=1),
                    ),
                    QueryHistory(
                        id=3,
                        user_id=7,
                        datasource_id=4,
                        question="其他数据源",
                        mode="agentic",
                        created_at=base,
                    ),
                    QueryHistory(
                        id=4,
                        user_id=7,
                        datasource_id=3,
                        question="业务问数",
                        mode="business",
                        created_at=base,
                    ),
                ]
            )
            db.commit()

            root_id = _resolve_parent_history_id(db, 2, 3, "agentic", SimpleNamespace(id=7))
            cross_datasource_id = _resolve_parent_history_id(db, 3, 3, "agentic", SimpleNamespace(id=7))
            cross_mode_id = _resolve_parent_history_id(db, 4, 3, "agentic", SimpleNamespace(id=7))

        self.assertEqual(root_id, 1)
        self.assertIsNone(cross_datasource_id)
        self.assertIsNone(cross_mode_id)


if __name__ == "__main__":
    unittest.main()
