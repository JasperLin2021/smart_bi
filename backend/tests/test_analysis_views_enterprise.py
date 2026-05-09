import os
import tempfile
import unittest
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


class AnalysisViewsEnterpriseTests(unittest.TestCase):
    def _db(self, tables):
        from app.db.base_class import Base

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine, tables=tables)
        return sessionmaker(bind=engine)()

    def _sqlite_sales_url(self):
        fd, path = tempfile.mkstemp(prefix="analysis-sales-", suffix=".db")
        os.close(fd)
        engine = create_engine(f"sqlite:///{path}")
        with engine.begin() as conn:
            conn.execute(text(
                """
                CREATE TABLE order_items (
                  order_id INTEGER,
                  customer_name TEXT,
                  product_category TEXT,
                  order_date TEXT,
                  quantity INTEGER,
                  revenue REAL
                )
                """
            ))
            conn.execute(
                text(
                    """
                    INSERT INTO order_items
                      (order_id, customer_name, product_category, order_date, quantity, revenue)
                    VALUES
                      (1, '长城汽车', '转向管柱总成', '2026-05-01', 5, 1200),
                      (2, '长城汽车', '电动助力模块', '2026-05-02', 5, 800),
                      (3, '理想汽车', '转向管柱总成', '2026-05-03', 5, 600),
                      (4, '奇瑞汽车', '传动轴', '2026-05-04', 3, 900),
                      (5, '奇瑞汽车', '传动轴', '2026-05-05', 5, 400)
                    """
                )
            )
        return f"sqlite:///{path}", path

    def _seed(self, db, database_url):
        from app.models.dashboard_config import Dashboard
        from app.models.dataset import Dataset
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from app.models.user import User

        db.add_all(
            [
                Organization(id=1, name="蓝途科技", slug="lantu"),
                Organization(id=2, name="外部组织", slug="external"),
                User(id=10, username="analyst", hashed_password="x", role="user", org_id=1),
                User(id=11, username="admin", hashed_password="x", role="org_admin", org_id=1),
                User(id=20, username="outsider", hashed_password="x", role="org_admin", org_id=2),
                DataSource(
                    id=100,
                    name="蓝途销售数据库",
                    slug="lantu-sales",
                    database_url=database_url,
                    source_type="database",
                    metadata_prompt="sales order items",
                    org_id=1,
                ),
                Dataset(
                    id=200,
                    name="蓝途科技销售数据",
                    datasource_id=100,
                    fields_json={
                        "table": "order_items",
                        "dimensions": [
                            {"name": "order_items.customer_name", "alias": "客户", "type": "string"},
                            {"name": "order_items.product_category", "alias": "产品线", "type": "string"},
                            {"name": "order_items.order_date", "alias": "下单日期", "type": "date"},
                        ],
                        "metrics": [
                            {"name": "order_items.revenue", "alias": "销售额", "aggregation": "sum", "type": "decimal"},
                            {"name": "order_items.quantity", "alias": "数量", "aggregation": "sum", "type": "integer"},
                        ],
                    },
                    aggregations_json={
                        "aggregations": [
                            {"field": "order_items.revenue", "aggregation": "sum", "alias": "销售额"},
                            {"field": "order_items.quantity", "aggregation": "sum", "alias": "数量"},
                        ]
                    },
                    status="published",
                    visibility="org",
                    org_id=1,
                    owner_id=10,
                ),
                Dashboard(
                    id=300,
                    title="销售经营看板",
                    layout_json={"components": []},
                    filters_json={},
                    status="draft",
                    visibility="private",
                    org_id=1,
                    owner_id=10,
                ),
            ]
        )
        db.commit()

    def test_draft_preview_executes_real_query_with_metrics_filter_sort_and_top_n(self):
        from app.api.analysis_views import preview_analysis_view_draft
        from app.models.analysis_view import AnalysisView
        from app.models.dashboard_config import Dashboard
        from app.models.dataset import Dataset
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from app.models.pinned_chart import PinnedChart
        from app.models.user import User
        from app.schemas.analysis_view import AnalysisDraftPreviewRequest

        database_url, path = self._sqlite_sales_url()
        try:
            db = self._db(
                [
                    User.__table__,
                    Organization.__table__,
                    DataSource.__table__,
                    Dataset.__table__,
                    AnalysisView.__table__,
                    Dashboard.__table__,
                    PinnedChart.__table__,
                ]
            )
            self._seed(db, database_url)

            result = preview_analysis_view_draft(
                AnalysisDraftPreviewRequest(
                    dataset_id=200,
                    chart_type="bar",
                    dimensions=["customer_name"],
                    measures=[{"field": "revenue", "aggregation": "sum", "alias": "销售额"}],
                    filters=[{"field": "quantity", "operator": "=", "value": 5}],
                    sorts=[{"field": "revenue", "direction": "desc"}],
                    visual_config_json={"top_n": 2},
                    calculation_fields_json={"calculations": ["ratio", "rank"]},
                    limit=50,
                ),
                db=db,
                current_user=SimpleNamespace(id=10, username="analyst", role="user", org_id=1),
            )

            self.assertEqual(result["dataset"]["name"], "蓝途科技销售数据")
            self.assertEqual(result["columns"][0], "customer_name")
            self.assertIn("销售额", result["columns"])
            self.assertEqual(len(result["rows"]), 2)
            self.assertEqual(result["rows"][0]["customer_name"], "长城汽车")
            self.assertEqual(result["rows"][0]["销售额"], 2000)
            self.assertIn("销售额_占比", result["columns"])
            self.assertIn("销售额_排名", result["columns"])
            self.assertEqual(result["query_plan"]["params"]["filter_0"], 5)
            self.assertIn("WHERE", result["query_plan"]["sql"])
            self.assertIn("GROUP BY", result["query_plan"]["sql"])
            self.assertIn("ORDER BY", result["query_plan"]["sql"])
            self.assertEqual(result["query_plan"]["limit"], 2)
            self.assertEqual(result["chart_data"]["series"][0]["name"], "销售额")
        finally:
            os.remove(path)

    def test_grouped_preview_can_sort_by_dataset_field_not_shown_in_result(self):
        from app.api.analysis_views import preview_analysis_view_draft
        from app.models.analysis_view import AnalysisView
        from app.models.dashboard_config import Dashboard
        from app.models.dataset import Dataset
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from app.models.pinned_chart import PinnedChart
        from app.models.user import User
        from app.schemas.analysis_view import AnalysisDraftPreviewRequest

        database_url, path = self._sqlite_sales_url()
        try:
            db = self._db(
                [
                    User.__table__,
                    Organization.__table__,
                    DataSource.__table__,
                    Dataset.__table__,
                    AnalysisView.__table__,
                    Dashboard.__table__,
                    PinnedChart.__table__,
                ]
            )
            self._seed(db, database_url)

            result = preview_analysis_view_draft(
                AnalysisDraftPreviewRequest(
                    dataset_id=200,
                    chart_type="line",
                    dimensions=["customer_name"],
                    measures=[{"field": "revenue", "aggregation": "sum", "alias": "销售额"}],
                    filters=[{"field": "quantity", "operator": "=", "value": 5}],
                    sorts=[{"field": "order_date", "direction": "asc"}],
                    limit=50,
                ),
                db=db,
                current_user=SimpleNamespace(id=10, username="analyst", role="user", org_id=1),
            )

            self.assertEqual(result["row_count"], 3)
            self.assertEqual(result["columns"], ["customer_name", "销售额"])
            self.assertIn("ORDER BY MIN", result["query_plan"]["sql"])
            self.assertIn("order_items.order_date", result["query_plan"]["sql"])
        finally:
            os.remove(path)

    def test_saved_preview_copy_publish_and_add_to_dashboard_enforce_scope(self):
        from app.api.analysis_views import (
            add_analysis_view_to_dashboard,
            copy_analysis_view,
            create_analysis_view,
            preview_analysis_view,
            publish_analysis_view,
        )
        from app.models.analysis_view import AnalysisView
        from app.models.dashboard_config import Dashboard
        from app.models.dataset import Dataset
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from app.models.pinned_chart import PinnedChart
        from app.models.user import User
        from app.schemas.analysis_view import (
            AnalysisDashboardAttachRequest,
            AnalysisPreviewRequest,
            AnalysisPublishRequest,
            AnalysisViewCreate,
        )

        database_url, path = self._sqlite_sales_url()
        try:
            db = self._db(
                [
                    User.__table__,
                    Organization.__table__,
                    DataSource.__table__,
                    Dataset.__table__,
                    AnalysisView.__table__,
                    Dashboard.__table__,
                    PinnedChart.__table__,
                ]
            )
            self._seed(db, database_url)
            analyst = SimpleNamespace(id=10, username="analyst", role="user", org_id=1)
            view = create_analysis_view(
                AnalysisViewCreate(
                    name="客户销售贡献",
                    dataset_id=200,
                    chart_type="bar",
                    dimensions=["customer_name"],
                    measures=[{"field": "revenue", "aggregation": "sum", "alias": "销售额"}],
                    filters=[{"field": "quantity", "operator": "=", "value": 5}],
                    sorts=[{"field": "revenue", "direction": "desc"}],
                    calculation_fields_json={"calculations": ["cumulative"]},
                    visual_config_json={"top_n": 3},
                ),
                db=db,
                current_user=analyst,
            )

            preview = preview_analysis_view(view.id, AnalysisPreviewRequest(limit=100), db=db, current_user=analyst)
            self.assertEqual(preview["row_count"], 3)
            self.assertIn("销售额_累计", preview["columns"])

            copied = copy_analysis_view(view.id, db=db, current_user=analyst)
            self.assertNotEqual(copied.id, view.id)
            self.assertIn("副本", copied.name)

            published = publish_analysis_view(
                view.id,
                AnalysisPublishRequest(status="published", visibility="org"),
                db=db,
                current_user=analyst,
            )
            self.assertEqual(published.status, "published")
            self.assertEqual(published.visibility, "org")

            response = add_analysis_view_to_dashboard(
                view.id,
                AnalysisDashboardAttachRequest(dashboard_id=300),
                db=db,
                current_user=analyst,
            )
            dashboard = db.query(Dashboard).filter(Dashboard.id == 300).one()
            chart = db.query(PinnedChart).one()
            self.assertEqual(response["dashboard_id"], 300)
            self.assertEqual(response["chart"]["id"], chart.id)
            self.assertEqual(dashboard.layout_json["components"][0]["analysis_view_id"], view.id)
            self.assertIn("SELECT", chart.sql_query)

            with self.assertRaises(HTTPException) as denied:
                preview_analysis_view(
                    view.id,
                    AnalysisPreviewRequest(limit=100),
                    db=db,
                    current_user=SimpleNamespace(id=20, username="outsider", role="org_admin", org_id=2),
                )
            self.assertEqual(denied.exception.status_code, 404)
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
