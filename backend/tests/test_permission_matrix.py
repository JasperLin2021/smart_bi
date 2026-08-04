import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class PermissionMatrixTests(unittest.TestCase):
    def _db(self):
        from app.db.base_class import Base
        from app.models.access_request import AccessRequest
        from app.models.action_item import ActionItem
        from app.models.alert import Alert
        from app.models.audit_log import AuditLog
        from app.models.big_screen import BigScreen
        from app.models.catalog import CatalogCategory, DataAsset
        from app.models.dashboard_comment import DashboardComment
        from app.models.dashboard_config import Dashboard
        from app.models.dataset import Dataset
        from app.models.datasource import DataSource
        from app.models.embed_token import EmbedToken
        from app.models.metric import Metric
        from app.models.organization import Organization
        from app.models.pinned_chart import PinnedChart
        from app.models.scheduled_report import ScheduledReport
        from app.models.user import User

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(
            bind=engine,
            tables=[
                Organization.__table__,
                User.__table__,
                AuditLog.__table__,
                DataSource.__table__,
                Dataset.__table__,
                Dashboard.__table__,
                BigScreen.__table__,
                Metric.__table__,
                Alert.__table__,
                ScheduledReport.__table__,
                CatalogCategory.__table__,
                DataAsset.__table__,
                ActionItem.__table__,
                AccessRequest.__table__,
                DashboardComment.__table__,
                PinnedChart.__table__,
                EmbedToken.__table__,
            ],
        )
        return sessionmaker(bind=engine)()

    def _seed_enterprise_matrix(self, db):
        from app.models.access_request import AccessRequest
        from app.models.alert import Alert
        from app.models.big_screen import BigScreen
        from app.models.catalog import DataAsset
        from app.models.dashboard_comment import DashboardComment
        from app.models.dashboard_config import Dashboard
        from app.models.dataset import Dataset
        from app.models.datasource import DataSource
        from app.models.metric import Metric
        from app.models.organization import Organization
        from app.models.pinned_chart import PinnedChart
        from app.models.scheduled_report import ScheduledReport
        from app.models.user import User

        nova = Organization(id=1, name="Nova Manufacturing", slug="nova-mfg")
        orion = Organization(id=2, name="Orion Retail Group", slug="orion-retail")
        root = User(id=1, username="root.ops", hashed_password="x", role="super_admin", org_id=None)
        nova_admin = User(id=10, username="nova.admin", hashed_password="x", role="org_admin", org_id=1)
        nova_analyst = User(id=11, username="nova.analyst", hashed_password="x", role="user", org_id=1)
        nova_finance = User(id=12, username="nova.finance", hashed_password="x", role="user", org_id=1)
        orion_admin = User(id=20, username="orion.admin", hashed_password="x", role="org_admin", org_id=2)
        orion_analyst = User(id=21, username="orion.analyst", hashed_password="x", role="user", org_id=2)

        nova_erp = DataSource(
            id=101,
            name="Nova ERP Warehouse",
            slug="nova-erp",
            database_url="sqlite:///nova_erp.db",
            source_type="sqlite",
            metadata_prompt="orders, inventory, production batches",
            org_id=1,
            is_active=1,
        )
        nova_quality = DataSource(
            id=102,
            name="Nova Quality Lake",
            slug="nova-quality",
            database_url="sqlite:///nova_quality.db",
            source_type="sqlite",
            metadata_prompt="inspection lots and yield records",
            org_id=1,
            is_active=1,
        )
        orion_pos = DataSource(
            id=201,
            name="Orion POS Mart",
            slug="orion-pos",
            database_url="sqlite:///orion_pos.db",
            source_type="sqlite",
            metadata_prompt="stores, receipts, basket lines",
            org_id=2,
            is_active=1,
        )

        nova_sales = Dataset(
            id=301,
            name="Nova Sales Fulfillment",
            description="Published order and fulfillment dataset for plant leadership.",
            datasource_id=101,
            fields_json={"table": "sales_orders", "fields": ["sales_orders.order_date", "sales_orders.amount"]},
            status="published",
            visibility="org",
            org_id=1,
            owner_id=11,
        )
        nova_margin_draft = Dataset(
            id=302,
            name="Nova Margin Working Draft",
            datasource_id=101,
            fields_json={"table": "margin_workbench", "fields": ["margin_workbench.sku"]},
            status="draft",
            visibility="private",
            org_id=1,
            owner_id=12,
        )
        orion_basket = Dataset(
            id=401,
            name="Orion Basket Analytics",
            datasource_id=201,
            fields_json={"table": "basket_lines", "fields": ["basket_lines.store_id"]},
            status="published",
            visibility="org",
            org_id=2,
            owner_id=21,
        )

        nova_dashboard = Dashboard(
            id=501,
            title="Nova Executive Operations",
            description="Daily revenue, backlog, and production overview.",
            layout_json={"components": []},
            status="published",
            visibility="org",
            org_id=1,
            owner_id=11,
            shared_user_ids=[12],
        )
        nova_private_dashboard = Dashboard(
            id=502,
            title="Nova Finance Draft",
            layout_json={"components": []},
            status="draft",
            visibility="private",
            org_id=1,
            owner_id=12,
        )
        orion_dashboard = Dashboard(
            id=601,
            title="Orion Store Performance",
            layout_json={"components": []},
            status="published",
            visibility="org",
            org_id=2,
            owner_id=21,
        )

        nova_screen = BigScreen(
            id=701,
            title="Nova Plant Floor Wallboard",
            canvas_json={"widgets": [{"type": "kpi", "metric": "yield"}]},
            status="published",
            visibility="org",
            org_id=1,
            owner_id=10,
        )
        orion_screen = BigScreen(
            id=801,
            title="Orion Regional Sales Wallboard",
            canvas_json={"widgets": [{"type": "bar", "metric": "gmv"}]},
            status="published",
            visibility="org",
            org_id=2,
            owner_id=20,
        )

        nova_metric = Metric(
            id=901,
            dataset_id=301,
            datasource_id=101,
            name="Nova On Time Shipment Rate",
            definition="On-time shipments divided by all shipments.",
            status="published",
            certification_status="certified",
        )
        orion_metric = Metric(
            id=902,
            dataset_id=401,
            datasource_id=201,
            name="Orion Same Store Sales",
            definition="Comparable store sales growth.",
            status="published",
            certification_status="certified",
        )

        nova_alert = Alert(id=1001, name="Nova SLA Risk", datasource_id=101, metric_id=901, created_by=10)
        orion_report = ScheduledReport(
            id=1101,
            name="Orion Daily GMV",
            datasource_id=201,
            question="Summarize GMV by region",
            created_by=20,
        )
        nova_asset = DataAsset(
            id=1201,
            asset_type="dataset",
            asset_id=301,
            name="Nova Sales Fulfillment",
            datasource_id=101,
            org_id=1,
            owner_id=11,
            status="published",
            metadata_json={"fields": {"fields": [{"name": "amount", "type": "decimal"}]}},
        )
        nova_private_asset = DataAsset(
            id=1202,
            asset_type="dataset",
            asset_id=302,
            name="Nova Margin Working Draft",
            datasource_id=101,
            org_id=1,
            owner_id=12,
            status="draft",
        )
        orion_asset = DataAsset(
            id=1301,
            asset_type="dataset",
            asset_id=401,
            name="Orion Basket Analytics",
            datasource_id=201,
            org_id=2,
            owner_id=21,
            status="published",
        )
        nova_request = AccessRequest(
            id=1401,
            requester_id=11,
            resource_type="dataset",
            resource_id=301,
            resource_name="Nova Sales Fulfillment",
            reason="Quarterly gross margin investigation",
            status="pending",
            org_id=1,
        )
        orion_request = AccessRequest(
            id=1402,
            requester_id=21,
            resource_type="datasource",
            resource_id=201,
            resource_name="Orion POS Mart",
            reason="Regional campaign attribution",
            status="pending",
            org_id=2,
        )
        nova_comment = DashboardComment(
            id=1501,
            dashboard_id=501,
            user_id=11,
            username="nova.analyst",
            content="Backlog risk moved to assembly line 4.",
        )
        nova_chart = PinnedChart(
            id=1601,
            user_id=11,
            datasource_id=101,
            title="Nova Weekly Revenue",
            sql_query="select week, revenue from finance_weekly",
            chart_type="line",
        )
        orion_chart = PinnedChart(
            id=1602,
            user_id=21,
            datasource_id=201,
            title="Orion Store GMV",
            sql_query="select store, gmv from store_daily",
            chart_type="bar",
        )

        db.add_all(
            [
                nova,
                orion,
                root,
                nova_admin,
                nova_analyst,
                nova_finance,
                orion_admin,
                orion_analyst,
                nova_erp,
                nova_quality,
                orion_pos,
                nova_sales,
                nova_margin_draft,
                orion_basket,
                nova_dashboard,
                nova_private_dashboard,
                orion_dashboard,
                nova_screen,
                orion_screen,
                nova_metric,
                orion_metric,
                nova_alert,
                orion_report,
                nova_asset,
                nova_private_asset,
                orion_asset,
                nova_request,
                orion_request,
                nova_comment,
                nova_chart,
                orion_chart,
            ]
        )
        db.commit()
        return {
            "root": root,
            "nova_admin": nova_admin,
            "nova_analyst": nova_analyst,
            "nova_finance": nova_finance,
            "orion_admin": orion_admin,
            "orion_analyst": orion_analyst,
            "nova_erp": nova_erp,
            "nova_quality": nova_quality,
            "orion_pos": orion_pos,
            "nova_sales": nova_sales,
            "nova_margin_draft": nova_margin_draft,
            "orion_basket": orion_basket,
            "nova_dashboard": nova_dashboard,
            "nova_private_dashboard": nova_private_dashboard,
            "orion_dashboard": orion_dashboard,
            "nova_screen": nova_screen,
            "orion_screen": orion_screen,
            "nova_metric": nova_metric,
            "orion_metric": orion_metric,
            "nova_request": nova_request,
            "orion_request": orion_request,
            "nova_comment": nova_comment,
            "nova_chart": nova_chart,
            "orion_chart": orion_chart,
        }

    def _assert_http(self, status_code, fn, *args, **kwargs):
        with self.assertRaises(HTTPException) as exc:
            fn(*args, **kwargs)
        self.assertEqual(exc.exception.status_code, status_code)

    def test_identity_and_admin_boundaries_are_role_and_org_scoped(self):
        from app.api.organization import list_organizations
        from app.api.users import create_user, list_users
        from app.schemas.user import UserCreate

        db = self._db()
        data = self._seed_enterprise_matrix(db)

        nova_users = list_users(db=db, current_user=data["nova_admin"])
        self.assertEqual({user["username"] for user in nova_users}, {"nova.admin", "nova.analyst", "nova.finance"})
        all_users = list_users(db=db, current_user=data["root"])
        self.assertEqual(len(all_users), 6)
        self._assert_http(403, list_users, db=db, current_user=data["nova_analyst"])
        self.assertEqual({org.slug for org in list_organizations(db=db, current_user=data["nova_admin"])}, {"nova-mfg"})
        self.assertEqual({org.slug for org in list_organizations(db=db, current_user=data["root"])}, {"nova-mfg", "orion-retail"})

        payload = UserCreate(username="orion.shadow", password="x", role="user", org_id=2)
        self._assert_http(403, create_user, payload, db=db, current_user=data["nova_admin"])

    def test_business_feature_lists_are_scoped_with_realistic_org_data(self):
        from app.api.big_screens import list_big_screens
        from app.api.catalog import list_assets
        from app.api.dashboards import list_dashboards
        from app.api.datasets import list_datasets
        from app.api.datasource import list_datasources
        from app.api.metrics import list_metrics

        db = self._db()
        data = self._seed_enterprise_matrix(db)

        self.assertEqual({ds["slug"] for ds in list_datasources(db=db, current_user=data["nova_admin"])}, {"nova-erp", "nova-quality"})
        self.assertEqual({ds["slug"] for ds in list_datasources(db=db, current_user=data["root"])}, {"nova-erp", "nova-quality", "orion-pos"})

        analyst_datasets = list_datasets(db=db, current_user=data["nova_analyst"])["items"]
        self.assertEqual({dataset.name for dataset in analyst_datasets}, {"Nova Sales Fulfillment"})
        admin_datasets = list_datasets(db=db, current_user=data["nova_admin"])["items"]
        self.assertEqual({dataset.name for dataset in admin_datasets}, {"Nova Sales Fulfillment", "Nova Margin Working Draft"})

        dashboards = list_dashboards(db=db, current_user=data["nova_analyst"])["items"]
        self.assertEqual({dashboard.title for dashboard in dashboards}, {"Nova Executive Operations"})
        screens = list_big_screens(db=db, current_user=data["nova_admin"])["items"]
        self.assertEqual({screen.title for screen in screens}, {"Nova Plant Floor Wallboard"})
        metrics = list_metrics(db=db, current_user=data["nova_admin"])["items"]
        self.assertEqual({metric.name for metric in metrics}, {"Nova On Time Shipment Rate"})
        assets = list_assets(db=db, current_user=data["nova_analyst"])["items"]
        self.assertEqual({asset.name for asset in assets}, {"Nova Sales Fulfillment"})

    def test_cross_org_creation_and_access_request_management_are_rejected(self):
        from app.api.access_requests import AccessRequestReview, cancel_access_request, review_access_request
        from app.api.action_items import create_action_item
        from app.api.alerts import create_alert
        from app.api.datasets import create_dataset
        from app.api.scheduled_reports import create_report
        from app.schemas.action_item import ActionItemCreate
        from app.schemas.alert import AlertCreate
        from app.schemas.dataset import DatasetCreate
        from app.schemas.scheduled_report import ScheduledReportCreate

        db = self._db()
        data = self._seed_enterprise_matrix(db)

        self._assert_http(
            403,
            create_dataset,
            DatasetCreate(
                name="Nova Attempted POS Blend",
                datasource_id=201,
                fields_json={"table": "basket_lines", "fields": ["basket_lines.store_id"]},
            ),
            db=db,
            current_user=data["nova_admin"],
        )
        self._assert_http(
            403,
            create_alert,
            AlertCreate(name="Cross Org GMV Alert", dataset_id=401, datasource_id=201),
            db=db,
            current_user=data["nova_admin"],
        )
        self._assert_http(
            403,
            create_report,
            ScheduledReportCreate(
                name="Cross Org POS Report",
                dataset_id=401,
                datasource_id=201,
                question="GMV by store",
            ),
            db=db,
            current_user=data["nova_admin"],
        )
        self._assert_http(
            403,
            create_action_item,
            ActionItemCreate(title="Review Orion basket mix", linked_dataset_id=401, source_type="dataset"),
            db=db,
            current_user=data["nova_admin"],
        )
        self._assert_http(
            404,
            review_access_request,
            1401,
            AccessRequestReview(status="approved"),
            db=db,
            current_user=data["orion_admin"],
        )
        self._assert_http(403, cancel_access_request, 1401, db=db, current_user=data["orion_admin"])

    def test_comment_delete_requires_dashboard_access_before_admin_override(self):
        from app.api.comments import delete_comment
        from app.models.dashboard_comment import DashboardComment

        db = self._db()
        data = self._seed_enterprise_matrix(db)

        self._assert_http(403, delete_comment, 501, 1501, db=db, current_user=data["orion_admin"])
        self.assertIsNotNone(db.query(DashboardComment).filter(DashboardComment.id == 1501).first())

        result = delete_comment(501, 1501, db=db, current_user=data["nova_admin"])
        self.assertEqual(result, {"status": "ok"})
        self.assertIsNone(db.query(DashboardComment).filter(DashboardComment.id == 1501).first())

    def test_embed_tokens_chart_preview_and_forecast_require_resource_scope(self):
        from app.api.embed import EmbedTokenCreate, create_embed_token
        from app.api.forecast import ForecastRequest, run_forecast
        from app.api.pinned_charts import PinnedChartCreate, PinnedChartPreviewRequest, create_pinned_chart, preview_pinned_chart

        db = self._db()
        data = self._seed_enterprise_matrix(db)

        self._assert_http(
            403,
            create_embed_token,
            EmbedTokenCreate(label="wrong dashboard", resource_type="dashboard", resource_id=601),
            db=db,
            current_user=data["nova_admin"],
        )
        self._assert_http(
            403,
            create_embed_token,
            EmbedTokenCreate(label="wrong chart", resource_type="chart", resource_id=1602),
            db=db,
            current_user=data["nova_analyst"],
        )

        own_token = create_embed_token(
            EmbedTokenCreate(label="ops dashboard", resource_type="dashboard", resource_id=501),
            db=db,
            current_user=data["nova_admin"],
        )
        self.assertEqual(own_token.resource_id, 501)
        self.assertEqual(own_token.created_by, 10)

        self._assert_http(
            403,
            create_pinned_chart,
            PinnedChartCreate(title="Wrong POS Chart", sql_query="select store, gmv from store_daily", datasource_id=201),
            db=db,
            current_user=data["nova_analyst"],
        )
        self._assert_http(
            403,
            preview_pinned_chart,
            PinnedChartPreviewRequest(sql_query="select store, gmv from store_daily", datasource_id=201),
            db=db,
            current_user=data["nova_analyst"],
        )
        self._assert_http(
            403,
            run_forecast,
            ForecastRequest(datasource_id=201, sql_query="select day, gmv from store_daily"),
            db=db,
            current_user=data["nova_analyst"],
        )


if __name__ == "__main__":
    unittest.main()
