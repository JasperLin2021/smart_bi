import unittest
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class DataAccessOverviewTests(unittest.TestCase):
    def _db(self):
        from app.db.base_class import Base
        from app.models.dataset import Dataset, DatasetRefreshLog
        from app.models.datasource import DataSource
        from app.models.organization import Organization

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(
            bind=engine,
            tables=[
                Organization.__table__,
                DataSource.__table__,
                Dataset.__table__,
                DatasetRefreshLog.__table__,
            ],
        )
        db = sessionmaker(bind=engine)()
        db.add_all(
            [
                Organization(id=1, name="Org A", slug="a"),
                Organization(id=2, name="Org B", slug="b"),
                DataSource(
                    id=1,
                    name="MySQL 订单库",
                    slug="mysql_orders",
                    database_url="mysql+pymysql://u:p@host/db",
                    source_type="mysql",
                    metadata_prompt="orders",
                    schema_metadata='{"tables": [{"name": "orders", "columns": []}]}',
                    org_id=1,
                    is_active=1,
                ),
                DataSource(
                    id=2,
                    name="Excel 预算",
                    slug="excel_budget",
                    database_url="/data/budget.xlsx",
                    source_type="excel",
                    metadata_prompt="budget",
                    org_id=1,
                    is_active=1,
                ),
                DataSource(
                    id=3,
                    name="Other Org",
                    slug="other_org",
                    database_url="sqlite:///x.db",
                    source_type="sqlite",
                    metadata_prompt="other",
                    schema_metadata='{"tables": []}',
                    org_id=2,
                    is_active=1,
                ),
                Dataset(
                    id=1,
                    name="订单分析",
                    datasource_id=1,
                    status="published",
                    visibility="org",
                    org_id=1,
                    materialization_status="ready",
                    last_refresh_status="success",
                    last_refresh_row_count=128,
                ),
                Dataset(
                    id=2,
                    name="预算草稿",
                    datasource_id=2,
                    status="draft",
                    visibility="private",
                    org_id=1,
                    last_refresh_status="error",
                    last_refresh_row_count=0,
                ),
                Dataset(
                    id=3,
                    name="其他企业数据集",
                    datasource_id=3,
                    status="published",
                    visibility="org",
                    org_id=2,
                    materialization_status="ready",
                    last_refresh_status="success",
                    last_refresh_row_count=8,
                ),
                DatasetRefreshLog(
                    id=1,
                    dataset_id=1,
                    status="success",
                    row_count=128,
                    message="刷新成功",
                    org_id=1,
                    triggered_by_id=10,
                ),
                DatasetRefreshLog(
                    id=2,
                    dataset_id=2,
                    status="error",
                    row_count=0,
                    message="刷新失败",
                    org_id=1,
                    triggered_by_id=10,
                ),
            ]
        )
        db.commit()
        return db

    def test_org_admin_sees_same_org_data_access_overview(self):
        from app.api.data_access import get_data_access_overview

        overview = get_data_access_overview(
            db=self._db(),
            current_user=SimpleNamespace(id=10, role="org_admin", org_id=1),
        )

        self.assertEqual(overview["datasources"]["total"], 2)
        self.assertEqual(overview["datasources"]["schema_ready"], 1)
        self.assertEqual(overview["datasets"]["total"], 2)
        self.assertEqual(overview["datasets"]["published"], 1)
        self.assertEqual(overview["sync_tasks"]["success"], 1)
        self.assertEqual(overview["sync_tasks"]["failed"], 1)
        self.assertEqual(overview["source_types"], [{"type": "excel", "count": 1}, {"type": "mysql", "count": 1}])
        self.assertEqual(overview["recent_refresh_logs"][0]["status"], "error")

    def test_super_admin_sees_all_data_access_assets(self):
        from app.api.data_access import get_data_access_overview

        overview = get_data_access_overview(
            db=self._db(),
            current_user=SimpleNamespace(id=1, role="super_admin", org_id=None),
        )

        self.assertEqual(overview["datasources"]["total"], 3)
        self.assertEqual(overview["datasets"]["total"], 3)
        self.assertEqual(overview["datasets"]["materialized"], 2)
