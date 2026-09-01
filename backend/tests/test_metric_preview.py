import os
import tempfile
import unittest
from types import SimpleNamespace

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


class MetricPreviewTests(unittest.TestCase):
    def _db(self, tables):
        from app.db.base_class import Base

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine, tables=tables)
        return sessionmaker(bind=engine)()

    def _source_database(self):
        fd, path = tempfile.mkstemp(prefix="metric-preview-", suffix=".db")
        os.close(fd)
        engine = create_engine(f"sqlite:///{path}")
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE sales (
                      id INTEGER PRIMARY KEY,
                      region TEXT NOT NULL,
                      status TEXT NOT NULL,
                      amount REAL NOT NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO sales (region, status, amount)
                    VALUES
                      ('华东', '已完成', 120),
                      ('华东', '已完成', 50),
                      ('华东', '已退款', 999),
                      ('华南', '已完成', 80)
                    """
                )
            )
        engine.dispose()
        return path

    def test_metric_preview_groups_live_data_by_selected_dimension(self):
        from app.api.metrics import preview_metric
        from app.models.dataset import Dataset
        from app.models.datasource import DataSource
        from app.models.metric import Metric
        from app.schemas.metric import MetricPreviewRequest

        source_path = self._source_database()
        try:
            db = self._db([DataSource.__table__, Dataset.__table__, Metric.__table__])
            datasource = DataSource(
                name="销售库",
                slug="sales-preview",
                source_type="database",
                database_url=f"sqlite:///{source_path}",
                metadata_prompt="",
                org_id=2,
            )
            db.add(datasource)
            db.flush()
            dataset = Dataset(
                name="销售订单",
                datasource_id=datasource.id,
                fields_json={
                    "table": "sales",
                    "dimensions": [{"name": "sales.region", "alias": "大区", "type": "string"}],
                    "metrics": [{"name": "sales.amount", "alias": "订单金额", "type": "decimal", "aggregation": "sum"}],
                },
                status="published",
                visibility="org",
                org_id=2,
                owner_id=10,
            )
            db.add(dataset)
            db.flush()
            metric = Metric(
                dataset_id=dataset.id,
                datasource_id=datasource.id,
                name="完成订单销售额",
                definition="已完成订单金额合计",
                formula="SUM(sales.amount)",
                column_name="sales.amount",
                aggregation="sum",
                calculation_config={
                    "calculation_mode": "aggregate",
                    "metric_field": "sales.amount",
                    "filters": [{"logic": "AND", "field": "sales.status", "operator": "=", "value": "已完成"}],
                },
                status="published",
                certification_status="certified",
                quality_status="normal",
            )
            db.add(metric)
            db.commit()
            db.refresh(metric)

            result = preview_metric(
                metric.id,
                MetricPreviewRequest(dimensions=["sales.region"], limit=10),
                db=db,
                current_user=SimpleNamespace(id=11, username="analyst", role="org_admin", org_id=2),
            )

            self.assertEqual(result["columns"], ["大区", "完成订单销售额"])
            self.assertEqual(result["rows"], [{"大区": "华东", "完成订单销售额": 170.0}, {"大区": "华南", "完成订单销售额": 80.0}])
            self.assertEqual(result["row_count"], 2)
            self.assertEqual(result["metric"]["name"], "完成订单销售额")
            self.assertEqual(result["query"]["dimensions"], ["sales.region"])
            self.assertIn("GROUP BY", result["query"]["sql"])
            self.assertIn("WHERE", result["query"]["sql"])
        finally:
            from app.db.session import _datasource_engines

            engine = _datasource_engines.pop(f"sqlite:///{source_path}", None)
            if engine is not None:
                engine.dispose()
            os.unlink(source_path)

    def test_metric_preview_supports_derived_column_dimensions(self):
        from app.api.metrics import preview_metric
        from app.models.dataset import Dataset
        from app.models.datasource import DataSource
        from app.models.metric import Metric
        from app.schemas.metric import MetricPreviewRequest

        source_path = self._source_database()
        try:
            db = self._db([DataSource.__table__, Dataset.__table__, Metric.__table__])
            datasource = DataSource(
                name="销售库",
                slug="sales-preview-derived",
                source_type="database",
                database_url=f"sqlite:///{source_path}",
                metadata_prompt="",
                org_id=2,
            )
            db.add(datasource)
            db.flush()
            dataset = Dataset(
                name="销售订单",
                datasource_id=datasource.id,
                fields_json={
                    "table": "sales",
                    "dimensions": [{"name": "sales.region", "alias": "大区", "type": "string"}],
                    "metrics": [{"name": "sales.amount", "alias": "订单金额", "type": "decimal", "aggregation": "sum"}],
                },
                derived_columns_json={"expressions": ["margin = sales.amount * 2"]},
                status="published",
                visibility="org",
                org_id=2,
                owner_id=10,
            )
            db.add(dataset)
            db.flush()
            metric = Metric(
                dataset_id=dataset.id,
                datasource_id=datasource.id,
                name="完成订单销售额",
                definition="已完成订单金额合计",
                formula="SUM(sales.amount)",
                column_name="sales.amount",
                aggregation="sum",
                calculation_config={
                    "calculation_mode": "aggregate",
                    "metric_field": "sales.amount",
                    "filters": [{"logic": "AND", "field": "sales.status", "operator": "=", "value": "已完成"}],
                },
                status="published",
                certification_status="certified",
                quality_status="normal",
            )
            db.add(metric)
            db.commit()
            db.refresh(metric)

            result = preview_metric(
                metric.id,
                MetricPreviewRequest(dimensions=["margin"], limit=10),
                db=db,
                current_user=SimpleNamespace(id=11, username="analyst", role="org_admin", org_id=2),
            )

            # 派生列以计算表达式参与 SELECT / GROUP BY，结果按指标倒序
            self.assertEqual(result["columns"], ["margin", "完成订单销售额"])
            self.assertEqual(
                result["rows"],
                [
                    {"margin": 240.0, "完成订单销售额": 120.0},
                    {"margin": 160.0, "完成订单销售额": 80.0},
                    {"margin": 100.0, "完成订单销售额": 50.0},
                ],
            )
            self.assertEqual(result["row_count"], 3)
            self.assertEqual(result["query"]["dimensions"], ["margin"])
            self.assertIn("amount * 2", result["query"]["sql"])
            self.assertIn("GROUP BY", result["query"]["sql"])
        finally:
            from app.db.session import _datasource_engines

            engine = _datasource_engines.pop(f"sqlite:///{source_path}", None)
            if engine is not None:
                engine.dispose()
            os.unlink(source_path)


    def _preview_fixture(self):
        """创建销售订单指标预览基础数据，返回 (db, metric, source_path)。"""
        # 导入 Organization 以注册 datasources.org_id 外键引用的表（自包含，不依赖其它测试的 import 副作用）
        from app.models.organization import Organization  # noqa: F401
        from app.models.dataset import Dataset
        from app.models.datasource import DataSource
        from app.models.metric import Metric

        source_path = self._source_database()
        db = self._db([DataSource.__table__, Dataset.__table__, Metric.__table__])
        datasource = DataSource(
            name="销售库",
            slug="sales-preview-sort",
            source_type="database",
            database_url=f"sqlite:///{source_path}",
            metadata_prompt="",
            org_id=2,
        )
        db.add(datasource)
        db.flush()
        dataset = Dataset(
            name="销售订单",
            datasource_id=datasource.id,
            fields_json={
                "table": "sales",
                "dimensions": [{"name": "sales.region", "alias": "大区", "type": "string"}],
                "metrics": [{"name": "sales.amount", "alias": "订单金额", "type": "decimal", "aggregation": "sum"}],
            },
            status="published",
            visibility="org",
            org_id=2,
            owner_id=10,
        )
        db.add(dataset)
        db.flush()
        metric = Metric(
            dataset_id=dataset.id,
            datasource_id=datasource.id,
            name="完成订单销售额",
            definition="已完成订单金额合计",
            formula="SUM(sales.amount)",
            column_name="sales.amount",
            aggregation="sum",
            calculation_config={
                "calculation_mode": "aggregate",
                "metric_field": "sales.amount",
                "filters": [{"logic": "AND", "field": "sales.status", "operator": "=", "value": "已完成"}],
            },
            status="published",
            certification_status="certified",
            quality_status="normal",
        )
        db.add(metric)
        db.commit()
        db.refresh(metric)
        return db, metric, source_path

    def _cleanup_preview(self, source_path):
        from app.db.session import _datasource_engines

        engine = _datasource_engines.pop(f"sqlite:///{source_path}", None)
        if engine is not None:
            engine.dispose()
        os.unlink(source_path)

    def _preview_with(self, db, metric, payload):
        from app.api.metrics import preview_metric

        return preview_metric(
            metric.id,
            payload,
            db=db,
            current_user=SimpleNamespace(id=11, username="analyst", role="org_admin", org_id=2),
        )

    def test_metric_preview_defaults_to_metric_desc_order(self):
        from app.schemas.metric import MetricPreviewRequest

        db, metric, source_path = self._preview_fixture()
        try:
            result = self._preview_with(db, metric, MetricPreviewRequest(dimensions=["sales.region"], limit=10))
            self.assertEqual(
                result["rows"],
                [{"大区": "华东", "完成订单销售额": 170.0}, {"大区": "华南", "完成订单销售额": 80.0}],
            )
            self.assertIn('ORDER BY "完成订单销售额" DESC', result["query"]["sql"])
            self.assertIsNone(result["query"]["order_by"])
            self.assertEqual(result["query"]["order_direction"], "desc")
        finally:
            self._cleanup_preview(source_path)

    def test_metric_preview_orders_by_dimension_field_asc(self):
        # SQLite 对中文按 UTF-8 字节序排序：华东 < 华南
        from app.schemas.metric import MetricPreviewRequest

        db, metric, source_path = self._preview_fixture()
        try:
            result = self._preview_with(
                db,
                metric,
                MetricPreviewRequest(
                    dimensions=["sales.region"],
                    limit=10,
                    order_by="sales.region",
                    order_direction="asc",
                ),
            )
            self.assertEqual(
                result["rows"],
                [{"大区": "华东", "完成订单销售额": 170.0}, {"大区": "华南", "完成订单销售额": 80.0}],
            )
            self.assertIn('ORDER BY "大区" ASC', result["query"]["sql"])
            self.assertEqual(result["query"]["order_by"], "sales.region")
            self.assertEqual(result["query"]["order_direction"], "asc")
        finally:
            self._cleanup_preview(source_path)

    def test_metric_preview_orders_by_dimension_label_desc(self):
        # 按维度输出别名"大区"降序，与默认指标降序产生不同行序，验证别名匹配与降序生效
        from app.schemas.metric import MetricPreviewRequest

        db, metric, source_path = self._preview_fixture()
        try:
            result = self._preview_with(
                db,
                metric,
                MetricPreviewRequest(
                    dimensions=["sales.region"],
                    limit=10,
                    order_by="大区",
                    order_direction="desc",
                ),
            )
            self.assertEqual(
                result["rows"],
                [{"大区": "华南", "完成订单销售额": 80.0}, {"大区": "华东", "完成订单销售额": 170.0}],
            )
            self.assertIn('ORDER BY "大区" DESC', result["query"]["sql"])
        finally:
            self._cleanup_preview(source_path)

    def test_metric_preview_orders_by_metric_asc(self):
        from app.schemas.metric import MetricPreviewRequest

        db, metric, source_path = self._preview_fixture()
        try:
            result = self._preview_with(
                db,
                metric,
                MetricPreviewRequest(
                    dimensions=["sales.region"],
                    limit=10,
                    order_by="完成订单销售额",
                    order_direction="asc",
                ),
            )
            self.assertEqual(
                result["rows"],
                [{"大区": "华南", "完成订单销售额": 80.0}, {"大区": "华东", "完成订单销售额": 170.0}],
            )
            self.assertIn('ORDER BY "完成订单销售额" ASC', result["query"]["sql"])
        finally:
            self._cleanup_preview(source_path)

    def test_metric_preview_rejects_invalid_order_field(self):
        from fastapi import HTTPException
        from app.schemas.metric import MetricPreviewRequest

        db, metric, source_path = self._preview_fixture()
        try:
            with self.assertRaises(HTTPException) as ctx:
                self._preview_with(
                    db,
                    metric,
                    MetricPreviewRequest(
                        dimensions=["sales.region"],
                        limit=10,
                        order_by="sales.status",
                    ),
                )
            self.assertEqual(ctx.exception.status_code, 400)
            self.assertIn("排序字段不合法", str(ctx.exception.detail))
        finally:
            self._cleanup_preview(source_path)

    def test_metric_preview_request_validates_order_direction(self):
        from pydantic import ValidationError
        from app.schemas.metric import MetricPreviewRequest

        with self.assertRaises(ValidationError):
            MetricPreviewRequest(dimensions=[], order_direction="random")
        request = MetricPreviewRequest(dimensions=[], order_direction="ASC")
        self.assertEqual(request.order_direction, "asc")


if __name__ == "__main__":
    unittest.main()
