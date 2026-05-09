import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


class QueryDatasetScopeTests(unittest.TestCase):
    def _db(self, tables):
        from app.db.base_class import Base
        from app.models.organization import Organization  # noqa: F401

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine, tables=tables)
        return sessionmaker(bind=engine)()

    def _source_database(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        engine = create_engine(f"sqlite:///{path}")
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE sales (region TEXT, amount INTEGER, status TEXT)"))
            conn.execute(
                text(
                    "INSERT INTO sales (region, amount, status) "
                    "VALUES ('East', 100, 'paid'), ('West', 80, 'pending')"
                )
            )
        engine.dispose()
        return path

    def test_query_ask_uses_dataset_context_and_bound_datasource(self):
        from app.api.query import ask
        from app.core.cache import init_cache
        from app.models.audit_log import AuditLog
        from app.models.dataset import Dataset
        from app.models.datasource import DataSource
        from app.models.query import QueryHistory
        from app.schemas.query import QueryAskRequest

        source_path = self._source_database()
        try:
            db = self._db([DataSource.__table__, Dataset.__table__, QueryHistory.__table__, AuditLog.__table__])
            datasource = DataSource(
                name="Sales DB",
                slug="sales-db",
                source_type="database",
                database_url=f"sqlite:///{source_path}",
                metadata_prompt="sales metadata",
                org_id=2,
            )
            db.add(datasource)
            db.flush()
            dataset = Dataset(
                name="Paid Sales Dataset",
                datasource_id=datasource.id,
                fields_json={"table": "sales", "fields": ["sales.region", "sales.amount"]},
                filters_json={"filters": ["sales.status = paid"]},
                status="published",
                visibility="org",
                org_id=2,
                owner_id=10,
            )
            db.add(dataset)
            db.commit()
            db.refresh(dataset)

            captured_context = {}

            async def fake_generate_safe_sql(
                question,
                datasource,
                query_plan=None,
                metric_match=None,
                context="",
            ):
                captured_context["datasource_id"] = datasource.id
                captured_context["context"] = context
                return "SELECT region, amount FROM sales WHERE status = 'paid'"

            async def fake_plan_query(_question, _datasource):
                return {"query_type": "detail"}

            async def fake_summary(_question, _result):
                return "ok"

            async def fake_get_llm_config():
                return {"model": "test"}

            init_cache()
            with (
                patch("app.api.query._generate_safe_sql", new=fake_generate_safe_sql),
                patch("app.api.query.plan_query", new=fake_plan_query),
                patch("app.api.query.match_metric_from_question", return_value=None),
                patch("app.api.query.generate_summary", new=fake_summary),
                patch("app.api.query.get_llm_config", new=fake_get_llm_config),
            ):
                import asyncio

                response = asyncio.run(
                    ask(
                        QueryAskRequest(question="按区域统计销售额", mode="text2sql", dataset_id=dataset.id),
                        db=db,
                        current_user=SimpleNamespace(id=99, username="analyst", role="user", org_id=2),
                    )
                )

            self.assertEqual(captured_context["datasource_id"], datasource.id)
            self.assertIn("当前选择数据集：Paid Sales Dataset", captured_context["context"])
            self.assertIn("主表：sales", captured_context["context"])
            self.assertIn("维度字段：sales.region, sales.amount", captured_context["context"])
            self.assertIn("固定筛选：sales.status = paid", captured_context["context"])
            self.assertEqual(response["result"]["rows"], [{"region": "East", "amount": 100}])
            self.assertEqual(db.query(QueryHistory).one().datasource_id, datasource.id)
        finally:
            os.unlink(source_path)


if __name__ == "__main__":
    unittest.main()
