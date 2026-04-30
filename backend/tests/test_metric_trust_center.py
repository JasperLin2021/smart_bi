import unittest
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class MetricTrustCenterTests(unittest.TestCase):
    def _db(self, tables):
        from app.db.base_class import Base
        from app.models.organization import Organization  # noqa: F401

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine, tables=tables)
        return sessionmaker(bind=engine)()

    def test_trusted_metric_fields_sync_to_catalog_metadata(self):
        from app.api.metrics import create_metric
        from app.models.audit_log import AuditLog
        from app.models.catalog import DataAsset
        from app.models.datasource import DataSource
        from app.models.metric import Metric
        from app.schemas.metric import MetricCreate

        db = self._db([DataSource.__table__, Metric.__table__, DataAsset.__table__, AuditLog.__table__])
        datasource = DataSource(
            name="Sales",
            slug="sales",
            database_url="sqlite:///:memory:",
            metadata_prompt="",
            org_id=2,
        )
        db.add(datasource)
        db.commit()
        db.refresh(datasource)

        metric = create_metric(
            MetricCreate(
                datasource_id=datasource.id,
                name="回款率",
                definition="已回款金额 / 应回款金额",
                formula="SUM(received_amount) / SUM(receivable_amount)",
                owner_name="财务负责人",
                unit="%",
                aggregation="ratio",
                tags=["财务", "核心"],
                status="published",
                certification_status="certified",
                caliber_version="v2026.04",
                quality_status="normal",
                quality_message="与财务月结口径一致",
                lineage_json={"source_tables": ["payments", "receivables"]},
            ),
            db=db,
            current_user=SimpleNamespace(id=1, username="root", role="super_admin", org_id=None),
        )

        self.assertEqual(metric.certification_status, "certified")
        self.assertEqual(metric.certified_by, "root")
        self.assertIsNotNone(metric.certified_at)
        self.assertEqual(metric.caliber_version, "v2026.04")
        self.assertEqual(metric.quality_status, "normal")

        asset = db.query(DataAsset).filter(DataAsset.asset_type == "metric", DataAsset.asset_id == metric.id).one()
        self.assertEqual(asset.metadata_json["certification_status"], "certified")
        self.assertEqual(asset.metadata_json["quality_status"], "normal")
        self.assertEqual(asset.metadata_json["caliber_version"], "v2026.04")
        self.assertEqual(asset.metadata_json["lineage"]["source_tables"], ["payments", "receivables"])

    def test_metric_lineage_returns_source_and_usage_nodes(self):
        from app.api.metrics import create_metric, get_metric_lineage
        from app.models.audit_log import AuditLog
        from app.models.catalog import DataAsset
        from app.models.datasource import DataSource
        from app.models.metric import Metric
        from app.schemas.metric import MetricCreate

        db = self._db([DataSource.__table__, Metric.__table__, DataAsset.__table__, AuditLog.__table__])
        datasource = DataSource(
            name="Sales",
            slug="sales",
            database_url="sqlite:///:memory:",
            metadata_prompt="",
            org_id=2,
        )
        db.add(datasource)
        db.commit()
        db.refresh(datasource)
        metric = create_metric(
            MetricCreate(
                datasource_id=datasource.id,
                name="销售额",
                definition="成交金额合计",
                formula="SUM(net_amount)",
                table_name="orders",
                column_name="net_amount",
                certification_status="pending_review",
                quality_status="stale",
            ),
            db=db,
            current_user=SimpleNamespace(id=1, username="root", role="super_admin", org_id=None),
        )

        lineage = get_metric_lineage(
            metric.id,
            db=db,
            current_user=SimpleNamespace(id=2, username="analyst", role="org_admin", org_id=2),
        )

        self.assertEqual(lineage["metric"]["name"], "销售额")
        self.assertEqual(lineage["datasource"]["name"], "Sales")
        self.assertEqual(lineage["source"]["table_name"], "orders")
        self.assertEqual(lineage["source"]["column_name"], "net_amount")
        self.assertEqual(lineage["trust"]["certification_status"], "pending_review")
        self.assertEqual(lineage["trust"]["quality_status"], "stale")

    def test_metric_list_is_scoped_to_user_org(self):
        from app.api.metrics import list_metrics
        from app.models.datasource import DataSource
        from app.models.metric import Metric

        db = self._db([DataSource.__table__, Metric.__table__])
        ds_same = DataSource(name="Same", slug="same", database_url="sqlite:///:memory:", metadata_prompt="", org_id=2)
        ds_other = DataSource(name="Other", slug="other", database_url="sqlite:///:memory:", metadata_prompt="", org_id=3)
        db.add_all([ds_same, ds_other])
        db.commit()
        db.refresh(ds_same)
        db.refresh(ds_other)
        db.add_all(
            [
                Metric(datasource_id=ds_same.id, name="同组织指标", definition="same"),
                Metric(datasource_id=ds_other.id, name="其他组织指标", definition="other"),
            ]
        )
        db.commit()

        result = list_metrics(
            db=db,
            current_user=SimpleNamespace(id=2, username="admin", role="org_admin", org_id=2),
        )

        self.assertEqual([item.name for item in result["items"]], ["同组织指标"])


if __name__ == "__main__":
    unittest.main()
