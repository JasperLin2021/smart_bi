import os
import tempfile
import unittest
from types import SimpleNamespace

import pandas as pd
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


class DatasetPipelineTests(unittest.TestCase):
    def _db(self, tables):
        from app.db.base_class import Base
        from app.models.organization import Organization  # noqa: F401

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine, tables=tables)
        return sessionmaker(bind=engine)()

    def _source_database(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        source_engine = create_engine(f"sqlite:///{path}")
        with source_engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE sales (
                      id INTEGER PRIMARY KEY,
                      region TEXT NOT NULL,
                      category TEXT NOT NULL,
                      amount INTEGER NOT NULL,
                      cost INTEGER NOT NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO sales (region, category, amount, cost)
                    VALUES
                      ('East', 'A', 100, 70),
                      ('West', 'A', 80, 50),
                      ('East', 'B', 130, 90)
                    """
                )
            )
        source_engine.dispose()
        return path

    def _excel_source_file(self):
        fd, path = tempfile.mkstemp(suffix=".xlsx")
        os.close(fd)
        pd.DataFrame(
            [
                {"item_id": "I001", "order_id": "O001", "quantity": 5, "unit_price": 100},
                {"item_id": "I002", "order_id": "O002", "quantity": 3, "unit_price": 80},
                {"item_id": "I003", "order_id": "O003", "quantity": 5, "unit_price": 120},
            ]
        ).to_excel(path, sheet_name="order_items", index=False)
        return path

    def _dataset_fixture(self, source_path: str):
        from app.models.audit_log import AuditLog
        from app.models.dataset import Dataset, DatasetRefreshLog
        from app.models.datasource import DataSource

        db = self._db([DataSource.__table__, Dataset.__table__, DatasetRefreshLog.__table__, AuditLog.__table__])
        datasource = DataSource(
            name="Sales DB",
            slug="sales-db",
            source_type="database",
            database_url=f"sqlite:///{source_path}",
            metadata_prompt="",
            org_id=2,
        )
        db.add(datasource)
        db.flush()
        dataset = Dataset(
            name="East Sales",
            datasource_id=datasource.id,
            fields_json={"table": "sales", "fields": ["sales.region", "sales.amount"]},
            filters_json={"filters": ["sales.region = East"]},
            derived_columns_json={"expressions": ["margin = sales.amount - sales.cost"]},
            status="draft",
            visibility="private",
            org_id=2,
            owner_id=10,
        )
        db.add(dataset)
        db.commit()
        db.refresh(dataset)
        return db, dataset

    def test_dataset_preview_executes_selected_fields_filters_and_derived_columns(self):
        from app.api.datasets import preview_dataset
        from app.schemas.dataset import DatasetPreviewRequest

        source_path = self._source_database()
        try:
            db, dataset = self._dataset_fixture(source_path)
            result = preview_dataset(
                dataset.id,
                DatasetPreviewRequest(limit=10),
                db=db,
                current_user=SimpleNamespace(id=10, username="owner", role="user", org_id=2),
            )

            self.assertEqual(result["columns"], ["region", "amount", "margin"])
            self.assertEqual(
                result["rows"],
                [
                    {"region": "East", "amount": 100, "margin": 30},
                    {"region": "East", "amount": 130, "margin": 40},
                ],
            )
            self.assertEqual(result["dataset_id"], dataset.id)
        finally:
            os.unlink(source_path)

    def test_dataset_draft_preview_applies_unsaved_filters_derived_columns_and_aggregations(self):
        from app.api.datasets import preview_dataset_draft
        from app.schemas.dataset import DatasetDraftPreviewRequest

        source_path = self._source_database()
        try:
            db, dataset = self._dataset_fixture(source_path)
            user = SimpleNamespace(id=10, username="owner", role="user", org_id=2)

            filtered = preview_dataset_draft(
                DatasetDraftPreviewRequest(
                    name="Unsaved East Sales",
                    datasource_id=dataset.datasource_id,
                    fields_json={"table": "sales", "fields": ["sales.region", "sales.amount"]},
                    filters_json={"filters": [{"field": "sales.region", "operator": "=", "value": "East"}]},
                    derived_columns_json={"expressions": ["margin = sales.amount - sales.cost"]},
                    limit=10,
                ),
                db=db,
                current_user=user,
            )

            self.assertEqual(filtered["dataset_id"], 0)
            self.assertEqual(filtered["columns"], ["region", "amount", "margin"])
            self.assertEqual(
                filtered["rows"],
                [
                    {"region": "East", "amount": 100, "margin": 30},
                    {"region": "East", "amount": 130, "margin": 40},
                ],
            )

            aggregated = preview_dataset_draft(
                DatasetDraftPreviewRequest(
                    name="Unsaved East Sales Summary",
                    datasource_id=dataset.datasource_id,
                    fields_json={"table": "sales", "fields": ["sales.region"]},
                    filters_json={"filters": ["sales.region = East"]},
                    aggregations_json={"aggregations": ["SUM(sales.amount)"]},
                    limit=10,
                ),
                db=db,
                current_user=user,
            )

            self.assertEqual(aggregated["columns"], ["region", "sum_amount"])
            self.assertEqual(aggregated["rows"], [{"region": "East", "sum_amount": 230}])

            metric_only = preview_dataset_draft(
                DatasetDraftPreviewRequest(
                    name="Unsaved Amount Summary",
                    datasource_id=dataset.datasource_id,
                    fields_json={"table": "sales", "fields": ["sales.amount"]},
                    aggregations_json={"aggregations": ["SUM(sales.amount)"]},
                    limit=10,
                ),
                db=db,
                current_user=user,
            )

            self.assertEqual(metric_only["columns"], ["sum_amount"])
            self.assertEqual(metric_only["rows"], [{"sum_amount": 310}])

            dimension_model = preview_dataset_draft(
                DatasetDraftPreviewRequest(
                    name="Unsaved Sales Dimensional Summary",
                    datasource_id=dataset.datasource_id,
                    fields_json={"table": "sales", "dimensions": ["sales.region"]},
                    filters_json={"filters": ["sales.region = East"]},
                    aggregations_json={"aggregations": ["SUM(sales.amount)"]},
                    limit=10,
                ),
                db=db,
                current_user=user,
            )

            self.assertEqual(dimension_model["columns"], ["region", "sum_amount"])
            self.assertEqual(dimension_model["rows"], [{"region": "East", "sum_amount": 230}])

            role_configured = preview_dataset_draft(
                DatasetDraftPreviewRequest(
                    name="Unsaved Sales Role Model",
                    datasource_id=dataset.datasource_id,
                    fields_json={
                        "table": "sales",
                        "dimensions": [{"field": "sales.region", "alias": "区域"}],
                        "metrics": [{"field": "sales.amount", "aggregation": "SUM", "alias": "销售额"}],
                    },
                    filters_json={"filters": ["sales.region = East"]},
                    aggregations_json={"aggregations": ["SUM(sales.amount)"]},
                    limit=10,
                ),
                db=db,
                current_user=user,
            )

            self.assertEqual(role_configured["columns"], ["区域", "销售额"])
            self.assertEqual(role_configured["rows"], [{"区域": "East", "销售额": 230}])
        finally:
            os.unlink(source_path)

    def test_derived_expression_allows_string_literal_percent_and_chinese(self):
        from app.api.datasets import preview_dataset_draft
        from app.schemas.dataset import DatasetDraftPreviewRequest

        source_path = self._source_database()
        try:
            db, dataset = self._dataset_fixture(source_path)
            user = SimpleNamespace(id=10, username="owner", role="user", org_id=2)

            result = preview_dataset_draft(
                DatasetDraftPreviewRequest(
                    name="含中文日期格式的派生列",
                    datasource_id=dataset.datasource_id,
                    fields_json={"table": "sales", "fields": ["sales.region", "sales.amount"]},
                    derived_columns_json={
                        "expressions": ["month_label = strftime('%Y年%m月', '2026-08-28')"]
                    },
                    limit=10,
                ),
                db=db,
                current_user=user,
            )

            self.assertEqual(result["columns"], ["region", "amount", "month_label"])
            self.assertEqual(
                result["rows"],
                [
                    {"region": "East", "amount": 100, "month_label": "2026年08月"},
                    {"region": "West", "amount": 80, "month_label": "2026年08月"},
                    {"region": "East", "amount": 130, "month_label": "2026年08月"},
                ],
            )
        finally:
            # Windows 下 SQLite 文件会被缓存的 engine 连接锁定，先释放再删除临时文件
            from app.db.session import get_datasource_engine

            get_datasource_engine(f"sqlite:///{source_path}").dispose()
            os.unlink(source_path)

    def test_derived_expression_allows_concat_and_time_format(self):
        """派生列应支持 || 字符串连接与 HH24:MI 之类的时间格式冒号（如 hour_label = strftime('%H:%M', ts) || '时'）。"""
        from app.api.datasets import preview_dataset_draft
        from app.schemas.dataset import DatasetDraftPreviewRequest

        source_path = self._source_database()
        try:
            db, dataset = self._dataset_fixture(source_path)
            user = SimpleNamespace(id=10, username="owner", role="user", org_id=2)

            result = preview_dataset_draft(
                DatasetDraftPreviewRequest(
                    name="含字符串连接与时间格式的派生列",
                    datasource_id=dataset.datasource_id,
                    fields_json={"table": "sales", "fields": ["sales.region", "sales.amount"]},
                    derived_columns_json={
                        "expressions": ["hour_label = strftime('%H:%M', '2026-08-28 14:30:00') || '时'"]
                    },
                    limit=10,
                ),
                db=db,
                current_user=user,
            )

            self.assertEqual(result["columns"], ["region", "amount", "hour_label"])
            self.assertEqual(
                result["rows"],
                [
                    {"region": "East", "amount": 100, "hour_label": "14:30时"},
                    {"region": "West", "amount": 80, "hour_label": "14:30时"},
                    {"region": "East", "amount": 130, "hour_label": "14:30时"},
                ],
            )
        finally:
            # Windows 下 SQLite 文件会被缓存的 engine 连接锁定，先释放再删除临时文件
            from app.db.session import get_datasource_engine

            get_datasource_engine(f"sqlite:///{source_path}").dispose()
            os.unlink(source_path)

    def test_excel_dataset_draft_preview_applies_filter_conditions(self):
        from app.api.datasets import preview_dataset_draft
        from app.models.datasource import DataSource
        from app.schemas.dataset import DatasetDraftPreviewRequest

        source_path = self._excel_source_file()
        try:
            db = self._db([DataSource.__table__])
            datasource = DataSource(
                name="蓝途科技销售数据",
                slug="blueway-demo-test",
                source_type="excel",
                database_url=source_path,
                metadata_prompt="",
                org_id=1,
            )
            db.add(datasource)
            db.commit()
            db.refresh(datasource)

            result = preview_dataset_draft(
                DatasetDraftPreviewRequest(
                    name="订单明细数量筛选",
                    datasource_id=datasource.id,
                    fields_json={
                        "table": "order_items",
                        "fields": ["order_items.item_id", "order_items.quantity", "order_items.unit_price"],
                    },
                    filters_json={"filters": ["order_items.quantity = 5"]},
                    limit=30,
                ),
                db=db,
                current_user=SimpleNamespace(id=2, username="nexteer_admin", role="org_admin", org_id=1),
            )

            self.assertEqual(result["columns"], ["item_id", "quantity", "unit_price"])
            self.assertEqual(
                result["rows"],
                [
                    {"item_id": "I001", "quantity": 5, "unit_price": 100},
                    {"item_id": "I003", "quantity": 5, "unit_price": 120},
                ],
            )

            derived = preview_dataset_draft(
                DatasetDraftPreviewRequest(
                    name="订单明细金额建模",
                    datasource_id=datasource.id,
                    fields_json={
                        "table": "order_items",
                        "fields": ["order_items.item_id", "order_items.quantity"],
                    },
                    filters_json={"filters": ["order_items.quantity = 5"]},
                    derived_columns_json={"expressions": ["line_total = order_items.quantity * order_items.unit_price"]},
                    limit=30,
                ),
                db=db,
                current_user=SimpleNamespace(id=2, username="nexteer_admin", role="org_admin", org_id=1),
            )

            self.assertEqual(derived["columns"], ["item_id", "quantity", "line_total"])
            self.assertEqual(
                derived["rows"],
                [
                    {"item_id": "I001", "quantity": 5, "line_total": 500},
                    {"item_id": "I003", "quantity": 5, "line_total": 600},
                ],
            )

            aggregated = preview_dataset_draft(
                DatasetDraftPreviewRequest(
                    name="订单明细数量汇总",
                    datasource_id=datasource.id,
                    fields_json={"table": "order_items", "fields": ["order_items.quantity"]},
                    filters_json={"filters": ["order_items.quantity = 5"]},
                    aggregations_json={"aggregations": ["SUM(order_items.unit_price)"]},
                    limit=30,
                ),
                db=db,
                current_user=SimpleNamespace(id=2, username="nexteer_admin", role="org_admin", org_id=1),
            )

            self.assertEqual(aggregated["columns"], ["quantity", "sum_unit_price"])
            self.assertEqual(aggregated["rows"], [{"quantity": 5, "sum_unit_price": 220}])

            distinct_orders = preview_dataset_draft(
                DatasetDraftPreviewRequest(
                    name="订单数去重汇总",
                    datasource_id=datasource.id,
                    fields_json={"table": "order_items", "fields": ["order_items.order_id"]},
                    aggregations_json={
                        "aggregations": [
                            {"field": "order_items.order_id", "aggregation": "count_distinct", "alias": "订单数"}
                        ]
                    },
                    limit=30,
                ),
                db=db,
                current_user=SimpleNamespace(id=2, username="nexteer_admin", role="org_admin", org_id=1),
            )

            self.assertEqual(distinct_orders["columns"], ["订单数"])
            self.assertEqual(distinct_orders["rows"], [{"订单数": 3}])

            grouped_distinct_orders = preview_dataset_draft(
                DatasetDraftPreviewRequest(
                    name="订单号维度去重汇总",
                    datasource_id=datasource.id,
                    fields_json={
                        "table": "order_items",
                        "dimensions": [{"name": "order_items.order_id", "alias": "订单号"}],
                    },
                    aggregations_json={
                        "aggregations": [
                            {"field": "order_items.order_id", "aggregation": "count_distinct", "alias": "订单数"}
                        ]
                    },
                    limit=30,
                ),
                db=db,
                current_user=SimpleNamespace(id=2, username="nexteer_admin", role="org_admin", org_id=1),
            )

            self.assertEqual(grouped_distinct_orders["columns"], ["订单号", "订单数"])
            self.assertEqual(
                sorted(grouped_distinct_orders["rows"], key=lambda row: row["订单号"]),
                [{"订单号": "O001", "订单数": 1}, {"订单号": "O002", "订单数": 1}, {"订单号": "O003", "订单数": 1}],
            )
        finally:
            os.unlink(source_path)

    def test_dataset_preview_is_scoped_to_user_org(self):
        from app.api.datasets import preview_dataset
        from app.schemas.dataset import DatasetPreviewRequest

        source_path = self._source_database()
        try:
            db, dataset = self._dataset_fixture(source_path)
            with self.assertRaises(HTTPException) as exc:
                preview_dataset(
                    dataset.id,
                    DatasetPreviewRequest(limit=10),
                    db=db,
                    current_user=SimpleNamespace(id=99, username="other", role="org_admin", org_id=3),
                )
            self.assertEqual(exc.exception.status_code, 404)
        finally:
            os.unlink(source_path)

    def test_dataset_refresh_writes_log_and_updates_dataset_status(self):
        from app.api.datasets import list_dataset_refresh_logs, refresh_dataset
        from app.models.dataset import DatasetRefreshLog

        source_path = self._source_database()
        try:
            db, dataset = self._dataset_fixture(source_path)
            user = SimpleNamespace(id=10, username="owner", role="user", org_id=2)

            result = refresh_dataset(dataset.id, db=db, current_user=user)
            logs = list_dataset_refresh_logs(dataset.id, db=db, current_user=user)

            self.assertEqual(result.status, "success")
            self.assertEqual(result.row_count, 2)
            self.assertEqual(dataset.last_refresh_status, "success")
            self.assertEqual(dataset.last_refresh_row_count, 2)
            self.assertIsNotNone(dataset.last_refresh_at)
            self.assertEqual(len(logs["items"]), 1)
            self.assertEqual(db.query(DatasetRefreshLog).count(), 1)
        finally:
            os.unlink(source_path)

    def test_org_visible_dataset_requires_department_admin_approval(self):
        from app.api.datasets import approve_dataset, create_dataset
        from app.models.audit_log import AuditLog
        from app.models.dataset import Dataset
        from app.models.datasource import DataSource
        from app.models.organization import Department, Organization
        from app.models.user import User
        from app.schemas.dataset import DatasetCreate

        db = self._db([
            Organization.__table__,
            Department.__table__,
            User.__table__,
            DataSource.__table__,
            Dataset.__table__,
            AuditLog.__table__,
        ])
        org = Organization(id=2, name="蓝途科技", slug="blueway")
        department = Department(id=21, name="销售运营部", org_id=2)
        owner = User(
            id=10,
            username="dataset_owner",
            hashed_password="x",
            role="user",
            org_id=2,
            department_id=21,
            department="销售运营部",
        )
        approver = User(
            id=11,
            username="dept_admin",
            hashed_password="x",
            role="dept_admin",
            org_id=2,
            department_id=21,
            department="销售运营部",
        )
        datasource = DataSource(
            name="Sales DB",
            slug="sales-db-approval",
            source_type="database",
            database_url="sqlite:///:memory:",
            metadata_prompt="",
            org_id=2,
        )
        db.add_all([org, department, owner, approver, datasource])
        db.commit()
        db.refresh(datasource)

        dataset = create_dataset(
            DatasetCreate(
                name="组织共享销售数据集",
                datasource_id=datasource.id,
                fields_json={"table": "sales", "fields": ["sales.region"]},
                visibility="org",
                status="published",
            ),
            db=db,
            current_user=owner,
        )

        self.assertEqual(dataset.visibility, "org")
        self.assertEqual(dataset.status, "pending_review")

        approved = approve_dataset(dataset.id, db=db, current_user=approver)

        self.assertEqual(approved.status, "published")
        self.assertEqual(approved.visibility, "org")


if __name__ == "__main__":
    unittest.main()
