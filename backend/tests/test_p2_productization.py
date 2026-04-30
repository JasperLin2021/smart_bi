import unittest
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class P2ProductizationTests(unittest.TestCase):
    def _db(self, tables):
        from app.db.base_class import Base

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine, tables=tables)
        return sessionmaker(bind=engine)()

    def test_organization_model_does_not_expose_commercial_package_fields(self):
        from app.models.organization import Organization

        for field in (
            "plan_type",
            "user_limit",
            "datasource_limit",
            "dashboard_limit",
            "big_screen_limit",
            "monthly_query_limit",
            "white_label_enabled",
            "branding_json",
        ):
            self.assertFalse(hasattr(Organization, field), field)

    def test_datasource_creation_stays_unlimited_for_each_org(self):
        from app.api.datasource import create_datasource
        from app.models.audit_log import AuditLog
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from app.schemas.datasource import DataSourceCreate

        db = self._db([Organization.__table__, DataSource.__table__, AuditLog.__table__])
        org = Organization(name="Acme", slug="acme")
        db.add(org)
        db.flush()
        db.add_all(
            [
                DataSource(
                    name=f"Existing {index}",
                    slug=f"existing-{index}",
                    database_url="sqlite:///:memory:",
                    metadata_prompt="",
                    org_id=org.id,
                )
                for index in range(10)
            ]
        )
        db.commit()

        created = create_datasource(
            DataSourceCreate(
                name="Next",
                slug="next",
                database_url="sqlite:///:memory:",
                metadata_prompt="",
                org_id=org.id,
            ),
            db=db,
            current_user=SimpleNamespace(id=1, username="root", role="super_admin", org_id=None),
        )

        self.assertEqual(created["name"], "Next")
        self.assertEqual(db.query(DataSource).filter(DataSource.org_id == org.id).count(), 11)

    def test_data_service_catalog_lists_metric_and_dashboard_contracts(self):
        from app.api.data_services import get_data_service_catalog
        from app.models.dashboard_config import Dashboard
        from app.models.datasource import DataSource
        from app.models.metric import Metric
        from app.models.organization import Organization

        db = self._db([Organization.__table__, DataSource.__table__, Metric.__table__, Dashboard.__table__])
        org = Organization(name="Acme", slug="acme")
        db.add(org)
        db.flush()
        ds = DataSource(name="Sales", slug="sales", database_url="sqlite:///:memory:", metadata_prompt="", org_id=org.id)
        db.add(ds)
        db.flush()
        metric = Metric(
            datasource_id=ds.id,
            name="GMV",
            definition="成交额",
            formula="SUM(amount)",
            status="published",
            certification_status="certified",
        )
        dashboard = Dashboard(title="经营看板", status="published", visibility="org", org_id=org.id, owner_id=2)
        db.add_all([metric, dashboard])
        db.commit()

        catalog = get_data_service_catalog(
            db=db,
            current_user=SimpleNamespace(id=2, username="admin", role="org_admin", org_id=org.id),
        )

        self.assertEqual(catalog["metrics"][0]["name"], "GMV")
        self.assertEqual(catalog["metrics"][0]["api_contract"]["endpoint"], f"/api/data-services/metrics/{metric.id}")
        self.assertEqual(catalog["dashboards"][0]["title"], "经营看板")
        self.assertIn("embed", catalog["sdk_examples"]["dashboard_embed"])

    def test_auto_insights_and_attribution_surface_business_drivers(self):
        from app.api.insights import (
            AnomalyAttributionRequest,
            AutoInsightsRequest,
            auto_insights,
            anomaly_attribution,
        )

        rows = [
            {"region": "华东", "month": "2026-01", "revenue": 120},
            {"region": "华南", "month": "2026-01", "revenue": 80},
            {"region": "华北", "month": "2026-01", "revenue": -30},
        ]

        insights = auto_insights(
            AutoInsightsRequest(columns=["region", "month", "revenue"], rows=rows),
            current_user=SimpleNamespace(id=1, username="analyst", role="user", org_id=1),
        )
        attribution = anomaly_attribution(
            AnomalyAttributionRequest(
                columns=["region", "month", "revenue"],
                rows=rows,
                metric_column="revenue",
                dimension_columns=["region"],
            ),
            current_user=SimpleNamespace(id=1, username="analyst", role="user", org_id=1),
        )

        self.assertGreaterEqual(len(insights["insights"]), 2)
        self.assertEqual(attribution["metric_column"], "revenue")
        self.assertEqual(attribution["drivers"][0]["dimension"], "region")
        self.assertEqual(attribution["drivers"][0]["value"], "华东")


if __name__ == "__main__":
    unittest.main()
