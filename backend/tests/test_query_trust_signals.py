import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


class QueryTrustSignalsTests(unittest.TestCase):
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
            conn.execute(text("CREATE TABLE receivables (received_amount INTEGER, receivable_amount INTEGER)"))
            conn.execute(text("INSERT INTO receivables VALUES (80, 100), (40, 100)"))
        engine.dispose()
        return path

    def test_query_response_returns_trust_signal_for_used_metric_formula(self):
        from app.api.query import ask, get_history_detail
        from app.core.cache import init_cache
        from app.models.audit_log import AuditLog
        from app.models.datasource import DataSource
        from app.models.metric import Metric
        from app.models.query import QueryHistory
        from app.schemas.query import QueryAskRequest

        source_path = self._source_database()
        try:
            db = self._db([DataSource.__table__, Metric.__table__, QueryHistory.__table__, AuditLog.__table__])
            datasource = DataSource(
                name="Finance",
                slug="finance",
                source_type="database",
                database_url=f"sqlite:///{source_path}",
                metadata_prompt="",
                org_id=2,
            )
            db.add(datasource)
            db.flush()
            metric = Metric(
                datasource_id=datasource.id,
                name="回款率",
                definition="已回款金额 / 应回款金额",
                formula="SUM(received_amount) / SUM(receivable_amount)",
                owner_name="财务负责人",
                unit="%",
                aggregation="ratio",
                status="published",
                certification_status="certified",
                certified_by="root",
                caliber_version="v2026.04",
                quality_status="normal",
                quality_message="与财务月结口径一致",
            )
            db.add(metric)
            db.commit()

            async def fake_generate_safe_sql(*_args, **_kwargs):
                return "SELECT SUM(received_amount) / SUM(receivable_amount) AS pay_rate FROM receivables"

            async def fake_plan_query(_question, _datasource):
                return {"query_type": "aggregate"}

            async def fake_summary(_question, _result):
                return "ok"

            async def fake_get_llm_config():
                return {"model": "test"}

            init_cache()
            with (
                patch("app.api.query._generate_safe_sql", new=fake_generate_safe_sql),
                patch("app.api.query.plan_query", new=fake_plan_query),
                patch(
                    "app.api.query.match_metric_from_question",
                    return_value={"name": "回款率", "formula": "SUM(received_amount) / SUM(receivable_amount)"},
                ),
                patch("app.api.query.generate_summary", new=fake_summary),
                patch("app.api.query.get_llm_config", new=fake_get_llm_config),
            ):
                import asyncio

                response = asyncio.run(
                    ask(
                        QueryAskRequest(question="查询回款率", mode="text2sql", datasource_id=datasource.id),
                        db=db,
                        current_user=SimpleNamespace(id=99, username="analyst", role="user", org_id=2),
                    )
                )

            self.assertEqual(response["trust_signals"][0]["metric_name"], "回款率")
            self.assertEqual(response["trust_signals"][0]["certification_status"], "certified")
            self.assertEqual(response["trust_signals"][0]["quality_status"], "normal")
            self.assertEqual(response["trust_signals"][0]["owner_name"], "财务负责人")
            self.assertEqual(response["trust_signals"][0]["caliber_version"], "v2026.04")

            history_detail = get_history_detail(
                response["history_id"],
                db=db,
                current_user=SimpleNamespace(id=99, username="analyst", role="user", org_id=2),
            )
            self.assertEqual(history_detail["trust_signals"][0]["metric_name"], "回款率")
        finally:
            os.unlink(source_path)


if __name__ == "__main__":
    unittest.main()
