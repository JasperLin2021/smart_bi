import unittest
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class P1P2CompletionTests(unittest.TestCase):
    def _db(self, tables):
        from app.db.base_class import Base
        from app.models.organization import Organization  # noqa: F401

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine, tables=tables)
        return sessionmaker(bind=engine)()

    def test_dataset_publish_syncs_catalog_asset(self):
        from app.api.datasets import create_dataset, publish_dataset
        from app.models.audit_log import AuditLog
        from app.models.catalog import DataAsset
        from app.models.dataset import Dataset
        from app.models.datasource import DataSource
        from app.schemas.dataset import DatasetCreate

        db = self._db([DataSource.__table__, Dataset.__table__, DataAsset.__table__, AuditLog.__table__])
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
        user = SimpleNamespace(id=10, username="analyst", role="org_admin", org_id=2)

        dataset = create_dataset(
            DatasetCreate(
                name="销售主题数据集",
                datasource_id=datasource.id,
                fields_json={"fields": ["region", "amount"]},
                filters_json={"status": "paid"},
            ),
            db=db,
            current_user=user,
        )
        publish_dataset(dataset.id, db=db, current_user=user)

        asset = db.query(DataAsset).filter(DataAsset.asset_type == "dataset", DataAsset.asset_id == dataset.id).one()
        self.assertEqual(asset.name, "销售主题数据集")
        self.assertEqual(asset.org_id, 2)
        self.assertEqual(asset.status, "published")

    def test_dashboard_share_creates_public_token_and_increments_version(self):
        from app.api.dashboards import create_dashboard, share_dashboard, update_dashboard
        from app.models.audit_log import AuditLog
        from app.models.catalog import DataAsset
        from app.models.dashboard_config import Dashboard
        from app.schemas.dashboard_center import DashboardCreate, DashboardShareUpdate, DashboardUpdate

        db = self._db([Dashboard.__table__, DataAsset.__table__, AuditLog.__table__])
        user = SimpleNamespace(id=10, username="owner", role="org_admin", org_id=2)
        dashboard = create_dashboard(
            DashboardCreate(title="经营看板", layout_json={"items": []}),
            db=db,
            current_user=user,
        )
        update_dashboard(
            dashboard.id,
            DashboardUpdate(description="v2"),
            db=db,
            current_user=user,
        )
        shared = share_dashboard(
            dashboard.id,
            DashboardShareUpdate(is_public=True, shared_user_ids=[20, 21]),
            db=db,
            current_user=user,
        )

        self.assertTrue(shared.is_public)
        self.assertTrue(shared.share_token)
        self.assertEqual(shared.shared_user_ids, [20, 21])
        self.assertEqual(shared.version, 2)

    def test_big_screen_publish_syncs_catalog_asset(self):
        from app.api.big_screens import create_big_screen, publish_big_screen
        from app.models.audit_log import AuditLog
        from app.models.big_screen import BigScreen
        from app.models.catalog import DataAsset
        from app.schemas.big_screen import BigScreenCreate

        db = self._db([BigScreen.__table__, DataAsset.__table__, AuditLog.__table__])
        user = SimpleNamespace(id=10, username="designer", role="org_admin", org_id=2)
        screen = create_big_screen(
            BigScreenCreate(title="销售大屏", canvas_json={"widgets": []}),
            db=db,
            current_user=user,
        )
        publish_big_screen(screen.id, db=db, current_user=user)

        asset = db.query(DataAsset).filter(DataAsset.asset_type == "big_screen", DataAsset.asset_id == screen.id).one()
        self.assertEqual(asset.name, "销售大屏")
        self.assertEqual(asset.status, "published")
        self.assertEqual(asset.org_id, 2)

    def test_operations_summary_counts_core_objects(self):
        from app.api.operations import get_operations_summary
        from app.models.audit_log import AuditLog
        from app.models.big_screen import BigScreen
        from app.models.catalog import DataAsset
        from app.models.dashboard_config import Dashboard
        from app.models.dataset import Dataset
        from app.models.query import QueryHistory
        from app.models.user import User

        db = self._db(
            [
                User.__table__,
                QueryHistory.__table__,
                DataAsset.__table__,
                Dashboard.__table__,
                Dataset.__table__,
                BigScreen.__table__,
                AuditLog.__table__,
            ]
        )
        db.add_all(
            [
                User(username="u1", hashed_password="x", role="user", org_id=2),
                QueryHistory(user_id=1, datasource_id=1, question="q"),
                DataAsset(asset_type="metric", name="销售额", org_id=2, status="published"),
                Dashboard(title="看板", org_id=2, status="published"),
                Dataset(name="数据集", datasource_id=1, org_id=2, status="published"),
                BigScreen(title="大屏", org_id=2, status="published"),
            ]
        )
        db.commit()

        summary = get_operations_summary(
            db=db,
            current_user=SimpleNamespace(id=1, username="admin", role="org_admin", org_id=2),
        )

        self.assertEqual(summary["active_users"], 1)
        self.assertEqual(summary["query_count"], 1)
        self.assertEqual(summary["asset_count"], 1)
        self.assertEqual(summary["dashboard_count"], 1)
        self.assertEqual(summary["dataset_count"], 1)
        self.assertEqual(summary["big_screen_count"], 1)


if __name__ == "__main__":
    unittest.main()
