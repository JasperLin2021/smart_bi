import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class OperationsUsageTests(unittest.TestCase):
    def _db(self):
        from app.db.base_class import Base
        from app.models.audit_log import AuditLog
        from app.models.big_screen import BigScreen
        from app.models.catalog import DataAsset
        from app.models.dashboard_config import Dashboard
        from app.models.dataset import Dataset, DatasetRefreshLog
        from app.models.datasource import DataSource
        from app.models.metric import Metric
        from app.models.organization import Organization
        from app.models.query import QueryHistory
        from app.models.user import User

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(
            bind=engine,
            tables=[
                Organization.__table__,
                User.__table__,
                DataSource.__table__,
                Dataset.__table__,
                DatasetRefreshLog.__table__,
                Dashboard.__table__,
                BigScreen.__table__,
                Metric.__table__,
                DataAsset.__table__,
                QueryHistory.__table__,
                AuditLog.__table__,
            ],
        )
        return sessionmaker(bind=engine)()

    def test_org_admin_summary_contains_scoped_resource_usage_and_recent_load(self):
        from app.api.operations import get_operations_summary
        from app.models.audit_log import AuditLog
        from app.models.big_screen import BigScreen
        from app.models.catalog import DataAsset
        from app.models.dashboard_config import Dashboard
        from app.models.dataset import Dataset, DatasetRefreshLog
        from app.models.datasource import DataSource
        from app.models.metric import Metric
        from app.models.organization import Organization
        from app.models.query import QueryHistory
        from app.models.user import User

        db = self._db()
        now = datetime.utcnow()
        org = Organization(name="蓝途科技", slug="lantu")
        other_org = Organization(name="外部企业", slug="external")
        db.add_all([org, other_org])
        db.flush()

        admin = User(id=10, username="lantu.admin", hashed_password="x", role="org_admin", org_id=org.id)
        analyst = User(id=11, username="lantu.analyst", hashed_password="x", role="user", org_id=org.id)
        outsider = User(id=20, username="external.user", hashed_password="x", role="user", org_id=other_org.id)
        db.add_all([admin, analyst, outsider])
        db.flush()

        sales_source = DataSource(
            name="蓝途销售库",
            slug="lantu-sales",
            database_url="sqlite:///:memory:",
            metadata_prompt="",
            org_id=org.id,
            is_active=1,
        )
        disabled_source = DataSource(
            name="停用库存库",
            slug="lantu-stock-disabled",
            database_url="sqlite:///:memory:",
            metadata_prompt="",
            org_id=org.id,
            is_active=0,
        )
        external_source = DataSource(
            name="外部销售库",
            slug="external-sales",
            database_url="sqlite:///:memory:",
            metadata_prompt="",
            org_id=other_org.id,
        )
        db.add_all([sales_source, disabled_source, external_source])
        db.flush()

        dataset = Dataset(
            name="销售明细数据集",
            datasource_id=sales_source.id,
            status="published",
            visibility="org",
            org_id=org.id,
            owner_id=admin.id,
            last_refresh_row_count=3200,
            last_refresh_status="success",
        )
        draft_dataset = Dataset(
            name="库存草稿数据集",
            datasource_id=disabled_source.id,
            status="draft",
            org_id=org.id,
            owner_id=admin.id,
        )
        external_dataset = Dataset(
            name="外部数据集",
            datasource_id=external_source.id,
            status="published",
            org_id=other_org.id,
            owner_id=outsider.id,
        )
        db.add_all([dataset, draft_dataset, external_dataset])
        db.flush()

        db.add_all(
            [
                Dashboard(title="经营驾驶舱", status="published", org_id=org.id, owner_id=admin.id),
                BigScreen(title="销售大屏", status="published", org_id=org.id, owner_id=admin.id),
                Metric(
                    dataset_id=dataset.id,
                    name="蓝途成交额",
                    definition="成交额",
                    formula="SUM(amount)",
                    status="published",
                    certification_status="certified",
                ),
                DataAsset(asset_type="dataset", asset_id=dataset.id, name="销售明细数据集", status="published", org_id=org.id),
                DataAsset(asset_type="dashboard", asset_id=1, name="经营驾驶舱", status="published", org_id=org.id),
                DataAsset(asset_type="dataset", asset_id=external_dataset.id, name="外部数据集", status="published", org_id=other_org.id),
                QueryHistory(
                    user_id=admin.id,
                    datasource_id=sales_source.id,
                    question="近七日销售额",
                    created_at=now - timedelta(days=1),
                    org_id=org.id,
                ),
                QueryHistory(
                    user_id=analyst.id,
                    datasource_id=sales_source.id,
                    question="昨日订单数",
                    created_at=now - timedelta(days=2),
                    org_id=org.id,
                ),
                QueryHistory(
                    user_id=analyst.id,
                    datasource_id=disabled_source.id,
                    question="历史库存",
                    created_at=now - timedelta(days=14),
                    org_id=org.id,
                ),
                QueryHistory(
                    user_id=outsider.id,
                    datasource_id=external_source.id,
                    question="外部查询",
                    created_at=now - timedelta(days=1),
                    org_id=other_org.id,
                ),
                AuditLog(
                    action="dataset.refresh",
                    resource_type="dataset",
                    status="error",
                    org_id=org.id,
                    created_at=now - timedelta(days=1),
                ),
                AuditLog(
                    action="dashboard.publish",
                    resource_type="dashboard",
                    status="success",
                    org_id=other_org.id,
                    created_at=now - timedelta(days=1),
                ),
                DatasetRefreshLog(
                    dataset_id=dataset.id,
                    status="failed",
                    row_count=0,
                    org_id=org.id,
                    created_at=now - timedelta(days=1),
                ),
            ]
        )
        db.commit()

        summary = get_operations_summary(
            db=db,
            current_user=SimpleNamespace(id=admin.id, username=admin.username, role="org_admin", org_id=org.id),
        )

        self.assertEqual(summary["scope"]["type"], "organization")
        self.assertEqual(summary["scope"]["org_id"], org.id)
        self.assertEqual(summary["active_users"], 2)
        self.assertEqual(summary["datasource_count"], 2)
        self.assertEqual(summary["dataset_count"], 2)
        self.assertEqual(summary["query_count"], 3)
        self.assertEqual(summary["workload"]["queries_7d"], 2)
        self.assertEqual(summary["workload"]["audit_errors_7d"], 1)
        self.assertEqual(summary["asset_health"]["inactive_datasources"], 1)
        self.assertEqual(summary["asset_health"]["dataset_refresh_failures_7d"], 1)
        self.assertEqual(summary["asset_health"]["published_assets"], 2)
        self.assertEqual(summary["asset_health"]["draft_datasets"], 1)
        self.assertEqual(summary["row_usage"]["dataset_rows"], 3200)
        self.assertIn("cpu_load", summary["system_resources"])
        self.assertIn("memory", summary["system_resources"])
        self.assertIn("disk", summary["system_resources"])
        self.assertGreaterEqual(summary["system_resources"]["memory"]["used_percent"], 0)
        self.assertLessEqual(summary["system_resources"]["memory"]["used_percent"], 100)
        self.assertEqual(summary["datasource_usage"][0]["name"], "蓝途销售库")
        self.assertEqual(summary["datasource_usage"][0]["query_count"], 2)
        self.assertEqual(len(summary["query_trend"]), 7)

        usage_by_key = {item["key"]: item for item in summary["resource_usage"]}
        self.assertEqual(usage_by_key["users"]["used"], 2)
        self.assertEqual(usage_by_key["datasources"]["used"], 2)
        self.assertEqual(usage_by_key["datasets"]["used"], 2)
        self.assertEqual(usage_by_key["dashboards"]["used"], 1)
        self.assertEqual(usage_by_key["metrics"]["used"], 1)

    def test_super_admin_summary_includes_all_organizations(self):
        from app.api.operations import get_operations_summary
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from app.models.user import User

        db = self._db()
        org_a = Organization(name="蓝途科技", slug="lantu")
        org_b = Organization(name="星河制造", slug="galaxy")
        db.add_all([org_a, org_b])
        db.flush()
        db.add_all(
            [
                User(username="root", hashed_password="x", role="super_admin", org_id=None),
                User(username="lantu.admin", hashed_password="x", role="org_admin", org_id=org_a.id),
                User(username="galaxy.admin", hashed_password="x", role="org_admin", org_id=org_b.id),
                DataSource(
                    name="蓝途销售库",
                    slug="lantu-sales",
                    database_url="sqlite:///:memory:",
                    metadata_prompt="",
                    org_id=org_a.id,
                ),
                DataSource(
                    name="星河质量库",
                    slug="galaxy-quality",
                    database_url="sqlite:///:memory:",
                    metadata_prompt="",
                    org_id=org_b.id,
                ),
            ]
        )
        db.commit()

        summary = get_operations_summary(
            db=db,
            current_user=SimpleNamespace(id=1, username="root", role="super_admin", org_id=None),
        )

        self.assertEqual(summary["scope"]["type"], "platform")
        self.assertEqual(summary["organization_count"], 2)
        self.assertEqual(summary["active_users"], 3)
        self.assertEqual(summary["datasource_count"], 2)

    def test_system_resources_degrades_when_getloadavg_unavailable(self):
        import os
        from unittest.mock import patch

        from app.api.operations import _system_resources

        # 模拟 Windows：os.getloadavg 属性不存在，存在性判断应直接降级为 0.0
        with patch.object(os, "getloadavg", None, create=True):
            resources = _system_resources()
        self.assertEqual(resources["cpu_load"]["used"], 0)
        self.assertEqual(resources["cpu_load"]["used_percent"], 0)
        self.assertIn("label", resources["cpu_load"])
        self.assertIn("detail", resources["cpu_load"])
        self.assertIn("memory", resources)
        self.assertIn("disk", resources)

        # 模拟属性存在但调用抛 AttributeError：异常兜底也应降级为 0.0
        with patch.object(os, "getloadavg", side_effect=AttributeError, create=True):
            resources = _system_resources()
        self.assertEqual(resources["cpu_load"]["used"], 0)
        self.assertEqual(resources["cpu_load"]["used_percent"], 0)
        self.assertIn("label", resources["cpu_load"])
        self.assertIn("detail", resources["cpu_load"])
        self.assertIn("memory", resources)
        self.assertIn("disk", resources)


if __name__ == "__main__":
    unittest.main()
