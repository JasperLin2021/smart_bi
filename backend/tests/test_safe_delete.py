import unittest
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class SafeDeleteTests(unittest.TestCase):
    def _db(self, tables):
        from app.db.base_class import Base
        from app.models.organization import Organization  # noqa: F401

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine, tables=tables)
        return sessionmaker(bind=engine)()

    def _super_admin(self):
        return SimpleNamespace(id=999, username="admin", role="super_admin", org_id=None)

    def test_datasource_delete_is_blocked_when_business_entities_reference_it(self):
        from app.api.datasource import delete_datasource
        from app.models.alert import Alert
        from app.models.dataset import Dataset
        from app.models.datasource import DataSource
        from app.models.metric import Metric
        from app.models.pinned_chart import PinnedChart
        from app.models.scheduled_report import ScheduledReport

        db = self._db([
            DataSource.__table__,
            Dataset.__table__,
            Metric.__table__,
            Alert.__table__,
            ScheduledReport.__table__,
            PinnedChart.__table__,
        ])
        datasource = DataSource(
            name="Sales",
            slug="sales",
            database_url="sqlite:///:memory:",
            metadata_prompt="",
            org_id=2,
        )
        db.add(datasource)
        db.flush()
        db.add_all([
            Dataset(name="Sales Dataset", datasource_id=datasource.id, org_id=2, owner_id=10),
            Metric(name="Revenue", definition="Revenue", datasource_id=datasource.id),
            Alert(name="Revenue Alert", datasource_id=datasource.id),
            ScheduledReport(name="Daily Revenue", datasource_id=datasource.id, question="revenue"),
            PinnedChart(user_id=10, datasource_id=datasource.id, title="Revenue Chart", sql_query="select 1"),
        ])
        db.commit()

        with self.assertRaises(HTTPException) as exc:
            delete_datasource(datasource.id, db=db, current_user=self._super_admin())

        self.assertEqual(exc.exception.status_code, 409)
        self.assertIn("无法删除数据源", exc.exception.detail)
        self.assertIn("数据集", exc.exception.detail)
        self.assertIn("指标", exc.exception.detail)
        self.assertIsNotNone(db.query(DataSource).filter(DataSource.id == datasource.id).first())

    def test_dataset_delete_is_blocked_when_metric_or_action_item_references_it(self):
        from app.api.datasets import delete_dataset
        from app.models.action_item import ActionItem
        from app.models.catalog import DataAsset
        from app.models.dataset import Dataset
        from app.models.metric import Metric

        db = self._db([Dataset.__table__, Metric.__table__, ActionItem.__table__, DataAsset.__table__])
        dataset = Dataset(name="Curated Sales", datasource_id=3, org_id=2, owner_id=10)
        db.add(dataset)
        db.flush()
        db.add_all([
            Metric(name="GMV", definition="GMV", datasource_id=3, dataset_id=dataset.id),
            ActionItem(title="Review dataset", linked_dataset_id=dataset.id, org_id=2, owner_id=10),
        ])
        db.commit()

        with self.assertRaises(HTTPException) as exc:
            delete_dataset(dataset.id, db=db, current_user=self._super_admin())

        self.assertEqual(exc.exception.status_code, 409)
        self.assertIn("无法删除数据集", exc.exception.detail)
        self.assertIn("指标", exc.exception.detail)
        self.assertIn("行动项", exc.exception.detail)
        self.assertIsNotNone(db.query(Dataset).filter(Dataset.id == dataset.id).first())

    def test_metric_delete_is_blocked_when_alert_or_action_item_references_it(self):
        from app.api.metrics import delete_metric
        from app.models.action_item import ActionItem
        from app.models.alert import Alert
        from app.models.catalog import DataAsset
        from app.models.datasource import DataSource
        from app.models.metric import Metric

        db = self._db([
            DataSource.__table__,
            Metric.__table__,
            Alert.__table__,
            ActionItem.__table__,
            DataAsset.__table__,
        ])
        datasource = DataSource(
            name="Ops",
            slug="ops",
            database_url="sqlite:///:memory:",
            metadata_prompt="",
            org_id=2,
        )
        db.add(datasource)
        db.flush()
        metric = Metric(name="Yield", definition="Yield", datasource_id=datasource.id)
        db.add(metric)
        db.flush()
        db.add_all([
            Alert(name="Yield Alert", datasource_id=datasource.id, metric_id=metric.id),
            ActionItem(title="Fix yield", linked_metric_id=metric.id, org_id=2, owner_id=10),
        ])
        db.commit()

        with self.assertRaises(HTTPException) as exc:
            delete_metric(metric.id, db=db, current_user=self._super_admin())

        self.assertEqual(exc.exception.status_code, 409)
        self.assertIn("无法删除指标", exc.exception.detail)
        self.assertIn("预警", exc.exception.detail)
        self.assertIn("行动项", exc.exception.detail)
        self.assertIsNotNone(db.query(Metric).filter(Metric.id == metric.id).first())

    def test_dashboard_delete_is_blocked_when_embed_token_or_action_item_references_it(self):
        from app.api.dashboards import delete_dashboard
        from app.models.action_item import ActionItem
        from app.models.catalog import DataAsset
        from app.models.dashboard_config import Dashboard
        from app.models.embed_token import EmbedToken

        db = self._db([Dashboard.__table__, ActionItem.__table__, EmbedToken.__table__, DataAsset.__table__])
        dashboard = Dashboard(title="Exec Dashboard", org_id=2, owner_id=10)
        db.add(dashboard)
        db.flush()
        db.add_all([
            ActionItem(title="Review dashboard", linked_dashboard_id=dashboard.id, org_id=2, owner_id=10),
            EmbedToken(token="token-1", resource_type="dashboard", resource_id=dashboard.id),
        ])
        db.commit()

        with self.assertRaises(HTTPException) as exc:
            delete_dashboard(dashboard.id, db=db, current_user=self._super_admin())

        self.assertEqual(exc.exception.status_code, 409)
        self.assertIn("无法删除看板", exc.exception.detail)
        self.assertIn("行动项", exc.exception.detail)
        self.assertIn("嵌入令牌", exc.exception.detail)
        self.assertIsNotNone(db.query(Dashboard).filter(Dashboard.id == dashboard.id).first())

    def test_pinned_chart_delete_is_blocked_when_dashboard_layout_references_it(self):
        from app.api.pinned_charts import delete_pinned_chart
        from app.models.dashboard_config import Dashboard
        from app.models.embed_token import EmbedToken
        from app.models.pinned_chart import PinnedChart

        db = self._db([PinnedChart.__table__, Dashboard.__table__, EmbedToken.__table__])
        chart = PinnedChart(user_id=10, datasource_id=2, title="Revenue Chart", sql_query="select 1")
        db.add(chart)
        db.flush()
        db.add_all([
            Dashboard(
                title="Sales Dashboard",
                org_id=2,
                owner_id=10,
                layout_json={"components": [{"id": "c1", "pinned_chart_id": chart.id}]},
            ),
            EmbedToken(token="chart-token", resource_type="chart", resource_id=chart.id),
        ])
        db.commit()

        with self.assertRaises(HTTPException) as exc:
            delete_pinned_chart(chart.id, db=db, current_user=SimpleNamespace(id=10, role="user", org_id=2))

        self.assertEqual(exc.exception.status_code, 409)
        self.assertIn("无法删除固定图表", exc.exception.detail)
        self.assertIn("看板", exc.exception.detail)
        self.assertIn("嵌入令牌", exc.exception.detail)
        self.assertIsNotNone(db.query(PinnedChart).filter(PinnedChart.id == chart.id).first())

    def test_user_delete_is_blocked_when_user_owns_business_entities(self):
        from app.api.users import delete_user
        from app.models.dashboard_config import Dashboard
        from app.models.dataset import Dataset
        from app.models.user import User

        db = self._db([User.__table__, Dataset.__table__, Dashboard.__table__])
        user = User(username="owner", hashed_password="x", role="user", org_id=2)
        db.add(user)
        db.flush()
        db.add_all([
            Dataset(name="Owned Dataset", datasource_id=3, org_id=2, owner_id=user.id),
            Dashboard(title="Shared Dashboard", org_id=2, owner_id=10, shared_user_ids=[user.id]),
        ])
        db.commit()

        with self.assertRaises(HTTPException) as exc:
            delete_user(user.id, db=db, current_user=self._super_admin())

        self.assertEqual(exc.exception.status_code, 409)
        self.assertIn("无法删除用户", exc.exception.detail)
        self.assertIn("数据集", exc.exception.detail)
        self.assertIn("共享看板", exc.exception.detail)
        self.assertIsNotNone(db.query(User).filter(User.id == user.id).first())

    def test_organization_delete_is_blocked_when_org_has_business_entities(self):
        from app.api.organization import delete_organization
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from app.models.user import User

        db = self._db([Organization.__table__, User.__table__, DataSource.__table__])
        org = Organization(name="Acme", slug="acme")
        db.add(org)
        db.flush()
        db.add_all([
            User(username="member", hashed_password="x", role="user", org_id=org.id),
            DataSource(name="Org DS", slug="org-ds", database_url="sqlite:///:memory:", metadata_prompt="", org_id=org.id),
        ])
        db.commit()

        with self.assertRaises(HTTPException) as exc:
            delete_organization(org.id, db=db, current_user=self._super_admin())

        self.assertEqual(exc.exception.status_code, 409)
        self.assertIn("无法删除企业", exc.exception.detail)
        self.assertIn("用户", exc.exception.detail)
        self.assertIn("数据源", exc.exception.detail)
        self.assertIsNotNone(db.query(Organization).filter(Organization.id == org.id).first())


if __name__ == "__main__":
    unittest.main()
