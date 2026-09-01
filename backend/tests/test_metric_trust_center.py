import unittest
from types import SimpleNamespace

from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class MetricTrustCenterTests(unittest.TestCase):
    def _db(self, tables):
        from app.db.base_class import Base
        from app.models.organization import Organization  # noqa: F401

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine, tables=tables)
        return sessionmaker(bind=engine)()

    def test_metric_input_requires_dataset_binding(self):
        from app.schemas.metric import MetricCreate, MetricUpdate

        with self.assertRaises(ValidationError):
            MetricCreate(
                datasource_id=1,
                name="旧数据源绑定指标",
                definition="不允许直接绑定数据源",
            )

        with self.assertRaises(ValidationError):
            MetricUpdate(datasource_id=1)

    def test_trusted_metric_fields_sync_to_catalog_metadata(self):
        from app.api.metrics import create_metric
        from app.models.audit_log import AuditLog
        from app.models.catalog import DataAsset
        from app.models.dataset import Dataset
        from app.models.datasource import DataSource
        from app.models.metric import Metric
        from app.schemas.metric import MetricCreate

        db = self._db([DataSource.__table__, Dataset.__table__, Metric.__table__, DataAsset.__table__, AuditLog.__table__])
        datasource = DataSource(
            name="Sales",
            slug="sales",
            database_url="sqlite:///:memory:",
            metadata_prompt="",
            org_id=2,
        )
        db.add(datasource)
        db.flush()
        db.refresh(datasource)
        dataset = Dataset(name="Sales Dataset", datasource_id=datasource.id, org_id=2, owner_id=1)
        db.add(dataset)
        db.commit()
        db.refresh(dataset)

        metric = create_metric(
            MetricCreate(
                dataset_id=dataset.id,
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

    def test_enterprise_calculation_config_syncs_to_metric_and_catalog(self):
        from app.api.metrics import create_metric, get_metric_lineage
        from app.models.audit_log import AuditLog
        from app.models.catalog import DataAsset
        from app.models.dataset import Dataset
        from app.models.datasource import DataSource
        from app.models.metric import Metric
        from app.schemas.metric import MetricCreate

        db = self._db([DataSource.__table__, Dataset.__table__, Metric.__table__, DataAsset.__table__, AuditLog.__table__])
        datasource = DataSource(
            name="Sales",
            slug="sales-enterprise-caliber",
            database_url="sqlite:///:memory:",
            metadata_prompt="",
            org_id=2,
        )
        db.add(datasource)
        db.flush()
        dataset = Dataset(
            name="Sales Dataset",
            datasource_id=datasource.id,
            fields_json={"table": "orders", "fields": ["orders.received_amount", "orders.receivable_amount"]},
            org_id=2,
            owner_id=1,
        )
        db.add(dataset)
        db.commit()
        db.refresh(dataset)

        calculation_config = {
            "calculation_mode": "ratio",
            "numerator_expression": "SUM(received_amount)",
            "denominator_expression": "SUM(receivable_amount)",
            "statistical_window": "自然月",
            "time_field": "order_date",
            "time_grain": "month",
            "filters": [
                {"logic": "AND", "field": "order_status", "operator": "=", "value": "已完成"}
            ],
            "null_handling": "金额为空按 0 处理",
            "dedup_key": "order_id",
            "denominator_zero_policy": "返回空值并标记风险",
            "decimal_precision": 4,
            "exception_handling": "排除退款与测试订单",
            "validation_rule": "与财务月结报表差异 <= 0.5%",
        }

        metric = create_metric(
            MetricCreate(
                dataset_id=dataset.id,
                name="企业级回款率",
                definition="已完成订单的回款金额 / 应回款金额",
                formula="SUM(received_amount) / NULLIF(SUM(receivable_amount), 0)",
                aggregation="ratio",
                calculation_config=calculation_config,
            ),
            db=db,
            current_user=SimpleNamespace(id=1, username="root", role="super_admin", org_id=None),
        )

        self.assertEqual(metric.calculation_config["calculation_mode"], "ratio")
        self.assertEqual(metric.calculation_config["filters"][0]["field"], "order_status")
        asset = db.query(DataAsset).filter(DataAsset.asset_type == "metric", DataAsset.asset_id == metric.id).one()
        self.assertEqual(asset.metadata_json["calculation_config"]["time_grain"], "month")
        self.assertEqual(asset.metadata_json["calculation_config"]["denominator_zero_policy"], "返回空值并标记风险")

        lineage = get_metric_lineage(
            metric.id,
            db=db,
            current_user=SimpleNamespace(id=2, username="analyst", role="org_admin", org_id=2),
        )
        self.assertEqual(lineage["metric"]["calculation_config"]["statistical_window"], "自然月")
        self.assertEqual(lineage["metric"]["calculation_config"]["filters"][0]["value"], "已完成")

    def test_metric_lineage_returns_source_and_usage_nodes(self):
        from app.api.metrics import create_metric, get_metric_lineage
        from app.models.audit_log import AuditLog
        from app.models.catalog import DataAsset
        from app.models.dataset import Dataset
        from app.models.datasource import DataSource
        from app.models.metric import Metric
        from app.schemas.metric import MetricCreate

        db = self._db([DataSource.__table__, Dataset.__table__, Metric.__table__, DataAsset.__table__, AuditLog.__table__])
        datasource = DataSource(
            name="Sales",
            slug="sales",
            database_url="sqlite:///:memory:",
            metadata_prompt="",
            org_id=2,
        )
        db.add(datasource)
        db.flush()
        db.refresh(datasource)
        dataset = Dataset(
            name="Sales Dataset",
            datasource_id=datasource.id,
            fields_json={"table": "orders", "fields": ["orders.net_amount"]},
            org_id=2,
            owner_id=1,
        )
        db.add(dataset)
        db.commit()
        db.refresh(dataset)
        metric = create_metric(
            MetricCreate(
                dataset_id=dataset.id,
                name="销售额",
                definition="成交金额合计",
                formula="SUM(net_amount)",
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
        self.assertEqual(lineage["dataset"]["name"], "Sales Dataset")
        self.assertEqual(lineage["datasource"]["name"], "Sales")
        self.assertEqual(lineage["source"]["table_name"], "orders")
        self.assertEqual(lineage["source"]["column_name"], "net_amount")
        self.assertEqual(lineage["trust"]["certification_status"], "pending_review")
        self.assertEqual(lineage["trust"]["quality_status"], "stale")

    def test_metric_lineage_uses_dataset_joins_json(self):
        from app.api.metrics import create_metric, get_metric_lineage
        from app.models.audit_log import AuditLog
        from app.models.catalog import DataAsset
        from app.models.dataset import Dataset
        from app.models.datasource import DataSource
        from app.models.metric import Metric
        from app.schemas.metric import MetricCreate

        db = self._db([DataSource.__table__, Dataset.__table__, Metric.__table__, DataAsset.__table__, AuditLog.__table__])
        datasource = DataSource(
            name="Sales",
            slug="sales-joins",
            database_url="sqlite:///:memory:",
            metadata_prompt="",
            org_id=2,
        )
        db.add(datasource)
        db.flush()
        dataset = Dataset(
            name="Sales Join Dataset",
            datasource_id=datasource.id,
            fields_json={"table": "orders", "metrics": ["orders.total_amount"]},
            joins_json=[
                {
                    "right": "customers",
                    "type": "LEFT JOIN",
                    "on": "orders.customer_id = customers.customer_id",
                }
            ],
            org_id=2,
            owner_id=1,
        )
        db.add(dataset)
        db.commit()
        db.refresh(dataset)

        metric = create_metric(
            MetricCreate(
                dataset_id=dataset.id,
                name="关联销售额",
                definition="已完成订单销售额",
                formula="SUM(orders.total_amount)",
                column_name="orders.total_amount",
                aggregation="sum",
                calculation_config={
                    "calculation_mode": "aggregate",
                    "metric_field": "orders.total_amount",
                    "statistical_window": "自然月",
                    "time_field": "orders.order_date",
                    "time_grain": "month",
                    "refresh_sla": "T+1 08:00 前完成刷新",
                },
            ),
            db=db,
            current_user=SimpleNamespace(id=1, username="root", role="super_admin", org_id=None),
        )

        lineage = get_metric_lineage(
            metric.id,
            db=db,
            current_user=SimpleNamespace(id=2, username="analyst", role="org_admin", org_id=2),
        )

        self.assertEqual(lineage["dataset"]["joins"][0]["table"], "customers")
        self.assertEqual(lineage["dataset"]["joins"][0]["join_type"], "LEFT JOIN")
        self.assertEqual(lineage["dataset"]["joins"][0]["join_on"], "orders.customer_id = customers.customer_id")

    def test_metric_lineage_exposes_statistical_scope_and_dependencies(self):
        from app.api.metrics import create_metric, get_metric_lineage
        from app.models.audit_log import AuditLog
        from app.models.catalog import DataAsset
        from app.models.dataset import Dataset
        from app.models.datasource import DataSource
        from app.models.metric import Metric
        from app.schemas.metric import MetricCreate

        db = self._db([DataSource.__table__, Dataset.__table__, Metric.__table__, DataAsset.__table__, AuditLog.__table__])
        datasource = DataSource(
            name="Sales",
            slug="sales-derived",
            database_url="sqlite:///:memory:",
            metadata_prompt="",
            org_id=2,
        )
        db.add(datasource)
        db.flush()
        dataset = Dataset(
            name="Sales Dataset",
            datasource_id=datasource.id,
            fields_json={
                "table": "orders",
                "metrics": ["orders.total_amount", "orders.order_id"],
                "dimensions": ["orders.region", "orders.order_date"],
            },
            org_id=2,
            owner_id=1,
        )
        db.add(dataset)
        db.commit()
        db.refresh(dataset)

        revenue = create_metric(
            MetricCreate(
                dataset_id=dataset.id,
                name="完成订单销售额",
                definition="已完成订单金额合计",
                formula="SUM(orders.total_amount)",
                column_name="orders.total_amount",
                aggregation="sum",
            ),
            db=db,
            current_user=SimpleNamespace(id=1, username="root", role="super_admin", org_id=None),
        )
        orders = create_metric(
            MetricCreate(
                dataset_id=dataset.id,
                name="完成订单数",
                definition="已完成订单去重数量",
                formula="COUNT(DISTINCT orders.order_id)",
                column_name="orders.order_id",
                aggregation="count_distinct",
            ),
            db=db,
            current_user=SimpleNamespace(id=1, username="root", role="super_admin", org_id=None),
        )
        metric = create_metric(
            MetricCreate(
                dataset_id=dataset.id,
                name="平均成交客单价",
                definition="完成订单销售额 / 完成订单数",
                formula="SUM(orders.total_amount) / NULLIF(COUNT(DISTINCT orders.order_id), 0)",
                column_name="avg_deal_amount",
                aggregation="custom",
                calculation_config={
                    "calculation_mode": "derived",
                    "derived_left_field": f"metric:{revenue.id}",
                    "derived_operator": "/",
                    "derived_right_field": f"metric:{orders.id}",
                    "dependency_metrics": "完成订单销售额, 完成订单数",
                    "statistical_window": "自然月",
                    "time_field": "orders.order_date",
                    "time_grain": "month",
                    "refresh_sla": "T+1 08:00 前完成刷新",
                    "filters": [
                        {"logic": "AND", "field": "orders.status", "operator": "=", "value": "已完成"}
                    ],
                    "statistical_scope": {
                        "included_subjects": ["已完成订单"],
                        "excluded_subjects": ["退款订单", "测试订单"],
                        "organization_scope": "蓝途科技销售组织",
                    },
                },
            ),
            db=db,
            current_user=SimpleNamespace(id=1, username="root", role="super_admin", org_id=None),
        )

        lineage = get_metric_lineage(
            metric.id,
            db=db,
            current_user=SimpleNamespace(id=2, username="analyst", role="org_admin", org_id=2),
        )

        self.assertEqual(lineage["scope"]["statistical_window"], "自然月")
        self.assertEqual(lineage["scope"]["time_field"], "orders.order_date")
        self.assertEqual(lineage["scope"]["filters"][0]["field"], "orders.status")
        self.assertEqual(lineage["scope"]["included_subjects"], ["已完成订单"])
        self.assertEqual(lineage["calculation"]["mode"], "derived")
        self.assertEqual([item["name"] for item in lineage["dependencies"]], ["完成订单销售额", "完成订单数"])

    def test_metric_lineage_resolves_advanced_derived_formula_dependencies(self):
        from app.api.metrics import _metric_source_fields, create_metric, get_metric_lineage
        from app.models.audit_log import AuditLog
        from app.models.catalog import DataAsset
        from app.models.dataset import Dataset
        from app.models.datasource import DataSource
        from app.models.metric import Metric
        from app.schemas.metric import MetricCreate

        db = self._db([DataSource.__table__, Dataset.__table__, Metric.__table__, DataAsset.__table__, AuditLog.__table__])
        datasource = DataSource(
            name="Sales",
            slug="sales-advanced-derived",
            database_url="sqlite:///:memory:",
            metadata_prompt="",
            org_id=2,
        )
        db.add(datasource)
        db.flush()
        dataset = Dataset(
            name="Sales Dataset",
            datasource_id=datasource.id,
            fields_json={
                "table": "orders",
                "metrics": ["orders.total_amount", "orders.order_id", "orders.delivery_completion"],
                "dimensions": ["orders.region", "orders.order_date"],
            },
            org_id=2,
            owner_id=1,
        )
        db.add(dataset)
        db.commit()
        db.refresh(dataset)

        revenue = create_metric(
            MetricCreate(
                dataset_id=dataset.id,
                name="完成订单销售额",
                definition="已完成订单金额合计",
                formula="SUM(orders.total_amount)",
                column_name="orders.total_amount",
                aggregation="sum",
            ),
            db=db,
            current_user=SimpleNamespace(id=1, username="root", role="super_admin", org_id=None),
        )
        orders = create_metric(
            MetricCreate(
                dataset_id=dataset.id,
                name="完成订单数",
                definition="已完成订单去重数量",
                formula="COUNT(DISTINCT orders.order_id)",
                column_name="orders.order_id",
                aggregation="count_distinct",
            ),
            db=db,
            current_user=SimpleNamespace(id=1, username="root", role="super_admin", org_id=None),
        )
        custom_expression = f"ROUND(metric:{revenue.id} / metric:{orders.id}, 2)"
        metric = create_metric(
            MetricCreate(
                dataset_id=dataset.id,
                name="平均成交客单价(高级公式)",
                definition="完成订单销售额 / 完成订单数",
                formula="ROUND(SUM(orders.total_amount) / NULLIF(COUNT(DISTINCT orders.order_id), 0), 2)",
                column_name="avg_deal_amount",
                aggregation="custom",
                calculation_config={
                    "calculation_mode": "derived",
                    "derived_formula_mode": "advanced",
                    "derived_custom_expression": custom_expression,
                    "dependency_metrics": "完成订单销售额, 完成订单数",
                    "statistical_window": "自然月",
                    "time_field": "orders.order_date",
                    "time_grain": "month",
                    "refresh_sla": "T+1 08:00 前完成刷新",
                },
            ),
            db=db,
            current_user=SimpleNamespace(id=1, username="root", role="super_admin", org_id=None),
        )

        lineage = get_metric_lineage(
            metric.id,
            db=db,
            current_user=SimpleNamespace(id=2, username="analyst", role="org_admin", org_id=2),
        )

        self.assertEqual(lineage["calculation"]["mode"], "derived")
        self.assertEqual(lineage["calculation"]["derived_formula_mode"], "advanced")
        self.assertEqual(lineage["calculation"]["derived_custom_expression"], custom_expression)
        self.assertEqual([item["name"] for item in lineage["dependencies"]], ["完成订单销售额", "完成订单数"])

        source_fields = _metric_source_fields(metric)
        self.assertIn("avg_deal_amount", source_fields)

    def test_expression_source_fields_skip_sql_keywords_and_metric_refs(self):
        from app.api.metrics import _expression_source_fields

        self.assertEqual(
            _expression_source_fields("ROUND(SUM(orders.delivery_completion)/COUNT(orders.order_id), 2)"),
            ["orders.delivery_completion", "orders.order_id"],
        )
        self.assertEqual(
            _expression_source_fields("ROUND(metric:5 / metric:6, 2)"),
            [],
        )
        self.assertEqual(_expression_source_fields(""), [])

    def test_metric_certifiers_are_permission_controlled_system_users(self):
        from app.api.metrics import list_metric_certifiers
        from app.models.organization import Organization
        from app.models.user import User

        db = self._db([Organization.__table__, User.__table__])
        org = Organization(name="Acme", slug="acme")
        db.add(org)
        db.flush()
        db.add_all(
            [
                User(username="root", hashed_password="x", role="super_admin", org_id=None),
                User(username="certifier", hashed_password="x", role="org_admin", org_id=org.id),
                User(username="viewer", hashed_password="x", role="user", org_id=org.id),
            ]
        )
        db.commit()

        result = list_metric_certifiers(
            db=db,
            current_user=SimpleNamespace(id=1, username="root", role="super_admin", org_id=None),
        )

        self.assertEqual([item["username"] for item in result["items"]], ["root", "certifier"])
        self.assertNotIn("viewer", [item["username"] for item in result["items"]])
        self.assertTrue(all(item["can_certify_metric"] for item in result["items"]))

    def test_create_metric_keeps_selected_certifier_from_same_org(self):
        from app.api.metrics import create_metric
        from app.models.audit_log import AuditLog
        from app.models.catalog import DataAsset
        from app.models.dataset import Dataset
        from app.models.datasource import DataSource
        from app.models.metric import Metric
        from app.models.organization import Organization
        from app.models.user import User
        from app.schemas.metric import MetricCreate

        db = self._db([
            Organization.__table__,
            User.__table__,
            DataSource.__table__,
            Dataset.__table__,
            Metric.__table__,
            DataAsset.__table__,
            AuditLog.__table__,
        ])
        org = Organization(name="Acme", slug="acme")
        db.add(org)
        db.flush()
        db.add(User(username="certifier", hashed_password="x", role="org_admin", org_id=org.id))
        datasource = DataSource(
            name="Sales",
            slug="sales",
            database_url="sqlite:///:memory:",
            metadata_prompt="",
            org_id=org.id,
        )
        db.add(datasource)
        db.flush()
        db.refresh(datasource)
        dataset = Dataset(name="Sales Dataset", datasource_id=datasource.id, org_id=org.id, owner_id=1)
        db.add(dataset)
        db.commit()
        db.refresh(dataset)

        metric = create_metric(
            MetricCreate(
                dataset_id=dataset.id,
                name="认证指标",
                definition="由系统用户认证",
                formula="SUM(amount)",
                certification_status="certified",
                certified_by="certifier",
            ),
            db=db,
            current_user=SimpleNamespace(id=1, username="root", role="super_admin", org_id=None),
        )

        self.assertEqual(metric.certified_by, "certifier")
        self.assertIsNotNone(metric.certified_at)

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

    def test_compute_metric_renders_dataset_joins_for_cross_table_formula(self):
        """跨表公式的指标在"计算指标"时需渲染数据集 JOIN 子句，避免 missing FROM-clause。"""
        from sqlalchemy import text as sql_text

        from app.api.metrics import compute_metric, create_metric
        from app.db.session import get_datasource_engine
        from app.models.audit_log import AuditLog
        from app.models.catalog import DataAsset
        from app.models.dataset import Dataset
        from app.models.datasource import DataSource
        from app.models.metric import Metric
        from app.schemas.metric import MetricCreate

        db = self._db([DataSource.__table__, Dataset.__table__, Metric.__table__, DataAsset.__table__, AuditLog.__table__])
        datasource = DataSource(
            name="CrossBorder",
            slug="cross-border-joins",
            database_url="sqlite:///:memory:",
            metadata_prompt="",
            org_id=2,
        )
        db.add(datasource)
        db.flush()
        dataset = Dataset(
            name="Cross Border Dataset",
            datasource_id=datasource.id,
            fields_json={"table": "orders", "metrics": ["order_payments.payment_value"]},
            joins_json=[
                {
                    "right": "order_payments",
                    "type": "LEFT JOIN",
                    "on": "orders.order_id = order_payments.order_id",
                }
            ],
            org_id=2,
            owner_id=1,
        )
        db.add(dataset)
        db.commit()
        db.refresh(dataset)

        metric = create_metric(
            MetricCreate(
                dataset_id=dataset.id,
                name="按州统计总GMV",
                definition="订单支付金额合计",
                formula="SUM(order_payments.payment_value)",
                aggregation="sum",
            ),
            db=db,
            current_user=SimpleNamespace(id=1, username="root", role="super_admin", org_id=None),
        )

        # 业务数据源建表并插入数据，get_datasource_engine 与 compute_metric 共用同一缓存引擎
        engine = get_datasource_engine(datasource.database_url)
        with engine.begin() as conn:
            conn.execute(sql_text("DROP TABLE IF EXISTS order_payments"))
            conn.execute(sql_text("DROP TABLE IF EXISTS orders"))
            conn.execute(sql_text("CREATE TABLE orders (order_id INTEGER PRIMARY KEY, customer_state VARCHAR(16))"))
            conn.execute(sql_text("CREATE TABLE order_payments (order_id INTEGER, payment_value NUMERIC)"))
            conn.execute(sql_text("INSERT INTO orders (order_id, customer_state) VALUES (1, 'CA'), (2, 'NY'), (3, 'CA')"))
            conn.execute(sql_text("INSERT INTO order_payments (order_id, payment_value) VALUES (1, 100), (1, 50), (2, 200), (3, 75)"))

        result = compute_metric(
            metric.id,
            db=db,
            current_user=SimpleNamespace(id=1, username="root", role="super_admin", org_id=None),
        )

        self.assertEqual(result["last_value"], 425.0)
        self.assertIsNotNone(result["computed_at"])
        db.refresh(metric)
        self.assertEqual(metric.last_value, 425.0)
        self.assertEqual(metric.quality_status, "normal")

        # 基线：数据集未配置 JOIN 时行为不变（不拼接 JOIN 子句）
        base_dataset = Dataset(
            name="Base No Join Dataset",
            datasource_id=datasource.id,
            fields_json={"table": "orders_base", "metrics": ["orders_base.total_amount"]},
            org_id=2,
            owner_id=1,
        )
        db.add(base_dataset)
        db.commit()
        db.refresh(base_dataset)
        base_metric = create_metric(
            MetricCreate(
                dataset_id=base_dataset.id,
                name="无 JOIN 基线指标",
                definition="订单金额合计",
                formula="SUM(total_amount)",
                aggregation="sum",
            ),
            db=db,
            current_user=SimpleNamespace(id=1, username="root", role="super_admin", org_id=None),
        )
        with engine.begin() as conn:
            conn.execute(sql_text("DROP TABLE IF EXISTS orders_base"))
            conn.execute(sql_text("CREATE TABLE orders_base (order_id INTEGER PRIMARY KEY, total_amount NUMERIC)"))
            conn.execute(sql_text("INSERT INTO orders_base (order_id, total_amount) VALUES (1, 10), (2, 20)"))

        base_result = compute_metric(
            base_metric.id,
            db=db,
            current_user=SimpleNamespace(id=1, username="root", role="super_admin", org_id=None),
        )
        self.assertEqual(base_result["last_value"], 30.0)


if __name__ == "__main__":
    unittest.main()
