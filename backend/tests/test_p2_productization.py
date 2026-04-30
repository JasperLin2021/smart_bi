import unittest
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class P2ProductizationTests(unittest.TestCase):
    def _db(self, tables):
        from app.db.base_class import Base

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine, tables=tables)
        return sessionmaker(bind=engine)()

    def test_org_usage_resolves_plan_limits_and_current_counts(self):
        from app.core.tenant_limits import get_organization_usage
        from app.models.big_screen import BigScreen
        from app.models.dashboard_config import Dashboard
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from app.models.query import QueryHistory
        from app.models.user import User

        db = self._db(
            [
                Organization.__table__,
                User.__table__,
                DataSource.__table__,
                Dashboard.__table__,
                BigScreen.__table__,
                QueryHistory.__table__,
            ]
        )
        org = Organization(
            name="Acme",
            slug="acme",
            plan_type="free",
            user_limit=3,
            datasource_limit=2,
            dashboard_limit=4,
            big_screen_limit=1,
            monthly_query_limit=10,
        )
        db.add(org)
        db.flush()
        db.add_all(
            [
                User(username="u1", hashed_password="x", org_id=org.id),
                DataSource(name="Sales", slug="sales", database_url="sqlite:///:memory:", metadata_prompt="", org_id=org.id),
                Dashboard(title="Board", org_id=org.id),
                BigScreen(title="Screen", org_id=org.id),
                QueryHistory(user_id=1, datasource_id=1, question="q"),
            ]
        )
        db.commit()

        usage = get_organization_usage(db, org.id)

        self.assertEqual(usage["plan_type"], "free")
        self.assertEqual(usage["limits"]["users"], 3)
        self.assertEqual(usage["usage"]["users"], 1)
        self.assertEqual(usage["usage"]["datasources"], 1)
        self.assertEqual(usage["remaining"]["big_screens"], 0)
        self.assertEqual(usage["remaining"]["monthly_queries"], 9)

    def test_datasource_creation_is_blocked_when_org_limit_is_reached(self):
        from app.api.datasource import create_datasource
        from app.models.audit_log import AuditLog
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from app.schemas.datasource import DataSourceCreate

        db = self._db([Organization.__table__, DataSource.__table__, AuditLog.__table__])
        org = Organization(name="Acme", slug="acme", datasource_limit=1)
        db.add(org)
        db.flush()
        db.add(DataSource(name="Existing", slug="existing", database_url="sqlite:///:memory:", metadata_prompt="", org_id=org.id))
        db.commit()

        with self.assertRaises(HTTPException) as raised:
            create_datasource(
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

        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("数据源", raised.exception.detail)

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
