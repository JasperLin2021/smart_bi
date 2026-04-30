import os
import tempfile
import unittest
from types import SimpleNamespace

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


class P0CompletionTests(unittest.TestCase):
    def _db(self, tables):
        from app.db.base_class import Base
        from app.models.organization import Organization  # noqa: F401

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine, tables=tables)
        return sessionmaker(bind=engine)()

    def test_preview_database_table_returns_rows_and_columns(self):
        from app.api.datasource import preview_datasource_table
        from app.models.audit_log import AuditLog
        from app.models.datasource import DataSource

        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            source_engine = create_engine(f"sqlite:///{path}")
            with source_engine.begin() as conn:
                conn.execute(text("CREATE TABLE sales (id INTEGER PRIMARY KEY, amount INTEGER)"))
                conn.execute(text("INSERT INTO sales (amount) VALUES (10), (20)"))
            source_engine.dispose()

            db = self._db([DataSource.__table__, AuditLog.__table__])
            ds = DataSource(
                name="Mock Sales",
                slug="mock-sales",
                source_type="database",
                database_url=f"sqlite:///{path}",
                metadata_prompt="",
                org_id=2,
            )
            db.add(ds)
            db.commit()
            db.refresh(ds)

            result = preview_datasource_table(
                ds.id,
                table="sales",
                limit=10,
                db=db,
                current_user=SimpleNamespace(id=11, username="admin", role="org_admin", org_id=2),
            )

            self.assertEqual(result["columns"], ["id", "amount"])
            self.assertEqual(result["rows"], [{"id": 1, "amount": 10}, {"id": 2, "amount": 20}])
            self.assertEqual(db.query(AuditLog).filter(AuditLog.action == "datasource.preview").count(), 1)
        finally:
            os.unlink(path)

    def test_metric_create_syncs_published_catalog_asset(self):
        from app.api.metrics import create_metric
        from app.models.audit_log import AuditLog
        from app.models.catalog import DataAsset
        from app.models.datasource import DataSource
        from app.models.metric import Metric
        from app.schemas.metric import MetricCreate

        db = self._db([DataSource.__table__, Metric.__table__, DataAsset.__table__, AuditLog.__table__])
        ds = DataSource(
            name="Mock Sales",
            slug="mock-sales",
            source_type="database",
            database_url="sqlite:///:memory:",
            metadata_prompt="",
            org_id=2,
        )
        db.add(ds)
        db.commit()
        db.refresh(ds)

        metric = create_metric(
            MetricCreate(
                datasource_id=ds.id,
                name="销售额",
                definition="成交金额合计",
                formula="SUM(net_amount)",
                owner_name="分析师",
                unit="元",
                aggregation="sum",
                tags=["销售"],
                status="published",
            ),
            db=db,
            current_user=SimpleNamespace(id=1, username="root", role="super_admin", org_id=None),
        )

        asset = db.query(DataAsset).filter(DataAsset.asset_type == "metric", DataAsset.asset_id == metric.id).one()
        self.assertEqual(asset.name, "销售额")
        self.assertEqual(asset.datasource_id, ds.id)
        self.assertEqual(asset.org_id, 2)
        self.assertEqual(asset.status, "published")
        self.assertEqual(asset.tags, ["销售"])

    def test_alerts_and_reports_are_limited_to_same_org_datasources(self):
        from app.api.alerts import list_alerts
        from app.api.scheduled_reports import list_reports
        from app.models.alert import Alert
        from app.models.datasource import DataSource
        from app.models.scheduled_report import ScheduledReport

        db = self._db([DataSource.__table__, Alert.__table__, ScheduledReport.__table__])
        same_ds = DataSource(name="Same", slug="same", database_url="sqlite:///:memory:", metadata_prompt="", org_id=2)
        other_ds = DataSource(name="Other", slug="other", database_url="sqlite:///:memory:", metadata_prompt="", org_id=1)
        db.add_all([same_ds, other_ds])
        db.commit()
        db.refresh(same_ds)
        db.refresh(other_ds)
        db.add_all(
            [
                Alert(name="same alert", datasource_id=same_ds.id),
                Alert(name="other alert", datasource_id=other_ds.id),
                ScheduledReport(name="same report", datasource_id=same_ds.id, question="q", cron_expression="0 9 * * *"),
                ScheduledReport(name="other report", datasource_id=other_ds.id, question="q", cron_expression="0 9 * * *"),
            ]
        )
        db.commit()

        user = SimpleNamespace(id=11, username="admin", role="org_admin", org_id=2)
        alerts = list_alerts(db=db, current_user=user)
        reports = list_reports(db=db, current_user=user)

        self.assertEqual([item.name for item in alerts["items"]], ["same alert"])
        self.assertEqual([item.name for item in reports["items"]], ["same report"])


if __name__ == "__main__":
    unittest.main()
