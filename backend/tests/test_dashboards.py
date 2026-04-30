import unittest
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class DashboardCenterTests(unittest.TestCase):
    def _db(self):
        from app.db.base_class import Base
        from app.models.catalog import DataAsset
        from app.models.dashboard_config import Dashboard
        from app.models.organization import Organization  # noqa: F401

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine, tables=[Dashboard.__table__, DataAsset.__table__])
        return sessionmaker(bind=engine)()

    def test_regular_user_sees_published_same_org_dashboards_and_own_drafts(self):
        from app.api.dashboards import list_dashboards
        from app.models.dashboard_config import Dashboard

        db = self._db()
        db.add_all(
            [
                Dashboard(title="经营看板", org_id=1, owner_id=20, status="published", visibility="org"),
                Dashboard(title="我的草稿", org_id=1, owner_id=10, status="draft", visibility="private"),
                Dashboard(title="其他组织", org_id=2, owner_id=30, status="published", visibility="org"),
                Dashboard(title="他人草稿", org_id=1, owner_id=20, status="draft", visibility="private"),
            ]
        )
        db.commit()

        result = list_dashboards(db=db, current_user=SimpleNamespace(id=10, role="user", org_id=1))

        self.assertEqual([item.title for item in result["items"]], ["我的草稿", "经营看板"])

    def test_publish_dashboard_creates_catalog_asset(self):
        from app.api.dashboards import publish_dashboard
        from app.models.catalog import DataAsset
        from app.models.dashboard_config import Dashboard

        db = self._db()
        dashboard = Dashboard(title="质量看板", description="质量跟踪", org_id=1, owner_id=20, status="draft")
        db.add(dashboard)
        db.commit()
        db.refresh(dashboard)

        result = publish_dashboard(
            dashboard.id,
            db=db,
            current_user=SimpleNamespace(id=11, role="org_admin", org_id=1),
        )

        assets = db.query(DataAsset).all()
        self.assertEqual(result.status, "published")
        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0].asset_type, "dashboard")
        self.assertEqual(assets[0].asset_id, dashboard.id)
        self.assertEqual(assets[0].status, "published")

    def test_update_dashboard_preserves_designer_layout_components(self):
        from app.api.dashboards import update_dashboard
        from app.models.dashboard_config import Dashboard
        from app.schemas.dashboard_center import DashboardUpdate

        db = self._db()
        dashboard = Dashboard(title="经营看板", org_id=1, owner_id=10, status="draft")
        db.add(dashboard)
        db.commit()
        db.refresh(dashboard)

        layout = {
            "components": [
                {
                    "id": "component-1",
                    "pinned_chart_id": 7,
                    "title": "良率趋势",
                    "chart_type": "line",
                    "x": 0,
                    "y": 0,
                    "w": 6,
                    "h": 3,
                }
            ]
        }

        result = update_dashboard(
            dashboard.id,
            DashboardUpdate(layout_json=layout, filters_json={"date": "this_month"}),
            db=db,
            current_user=SimpleNamespace(id=10, role="user", org_id=1),
        )

        self.assertEqual(result.layout_json, layout)
        self.assertEqual(result.filters_json, {"date": "this_month"})


if __name__ == "__main__":
    unittest.main()
