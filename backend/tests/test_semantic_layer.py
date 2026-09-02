import os
import tempfile
import unittest
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


class SemanticLayerTests(unittest.TestCase):
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
                      region TEXT NOT NULL,
                      status TEXT NOT NULL,
                      amount INTEGER NOT NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO sales (region, status, amount)
                    VALUES
                      ('East', 'paid', 100),
                      ('West', 'paid', 80),
                      ('East', 'pending', 20)
                    """
                )
            )
        source_engine.dispose()
        return path

    def _dataset_fixture(self, source_path: str):
        from app.models.audit_log import AuditLog
        from app.models.dataset import Dataset
        from app.models.datasource import DataSource

        db = self._db([DataSource.__table__, Dataset.__table__, AuditLog.__table__])
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
            name="Sales Semantic Dataset",
            datasource_id=datasource.id,
            fields_json={"table": "sales", "fields": ["sales.region", "sales.status", "sales.amount"]},
            filters_json={"filters": ["sales.status = paid"]},
            semantic_model_json={
                "dimensions": [
                    {"id": "region", "field": "sales.region", "label": "区域"},
                ],
                "metrics": [
                    {"id": "total_amount", "field": "sales.amount", "label": "销售额", "aggregation": "sum"},
                ],
                "time_dimensions": [],
                "synonyms": [{"term": "营收", "target_id": "total_amount"}],
            },
            status="published",
            visibility="org",
            org_id=2,
            owner_id=10,
        )
        db.add(dataset)
        db.commit()
        db.refresh(dataset)
        return db, dataset

    def test_dataset_semantic_model_round_trip_and_validation(self):
        from app.api.datasets import get_dataset_semantic_model, update_dataset_semantic_model
        from app.models.dataset import Dataset
        from app.schemas.dataset import DatasetSemanticModelUpdate

        source_path = self._source_database()
        try:
            db, dataset = self._dataset_fixture(source_path)
            user = SimpleNamespace(id=10, username="owner", role="user", org_id=2)

            response = get_dataset_semantic_model(dataset.id, db=db, current_user=user)
            self.assertEqual(response["semantic_model"]["dimensions"][0]["id"], "region")

            updated = update_dataset_semantic_model(
                dataset.id,
                DatasetSemanticModelUpdate(
                    semantic_model={
                        "dimensions": [{"id": "region", "field": "sales.region", "label": "区域"}],
                        "metrics": [
                            {"id": "avg_amount", "field": "sales.amount", "label": "平均销售额", "aggregation": "avg"}
                        ],
                        "time_dimensions": [],
                        "synonyms": [],
                    }
                ),
                db=db,
                current_user=user,
            )

            self.assertEqual(updated["semantic_model"]["metrics"][0]["id"], "avg_amount")
            self.assertEqual(db.query(Dataset).one().semantic_model_json["metrics"][0]["aggregation"], "avg")
        finally:
            os.unlink(source_path)

    def test_duplicate_semantic_ids_are_rejected(self):
        from app.api.datasets import update_dataset_semantic_model
        from app.schemas.dataset import DatasetSemanticModelUpdate

        source_path = self._source_database()
        try:
            db, dataset = self._dataset_fixture(source_path)
            with self.assertRaises(HTTPException) as exc:
                update_dataset_semantic_model(
                    dataset.id,
                    DatasetSemanticModelUpdate(
                        semantic_model={
                            "dimensions": [
                                {"id": "region", "field": "sales.region", "label": "区域"},
                            ],
                            "metrics": [
                                {"id": "region", "field": "sales.amount", "label": "销售额", "aggregation": "sum"}
                            ],
                        }
                    ),
                    db=db,
                    current_user=SimpleNamespace(id=10, username="owner", role="user", org_id=2),
                )
            self.assertEqual(exc.exception.status_code, 400)
        finally:
            os.unlink(source_path)

    def test_inferred_semantic_model_uses_dataset_dimensions_and_metrics(self):
        from app.api.datasets import get_dataset_semantic_model

        source_path = self._source_database()
        try:
            db, dataset = self._dataset_fixture(source_path)
            dataset.semantic_model_json = None
            dataset.fields_json = {"table": "sales", "dimensions": ["sales.region", "sales.status"]}
            dataset.aggregations_json = {"aggregations": ["SUM(sales.amount)"]}
            db.commit()

            response = get_dataset_semantic_model(
                dataset.id,
                db=db,
                current_user=SimpleNamespace(id=10, username="owner", role="user", org_id=2),
            )

            self.assertEqual([item["id"] for item in response["semantic_model"]["dimensions"]], ["region", "status"])
            self.assertEqual(response["semantic_model"]["metrics"][0]["id"], "sum_amount")

            dataset.fields_json = {
                "table": "sales",
                "dimensions": [{"field": "sales.region", "alias": "区域"}],
                "metrics": [{"field": "sales.amount", "aggregation": "AVG", "alias": "平均销售额"}],
            }
            dataset.aggregations_json = None
            db.commit()

            structured = get_dataset_semantic_model(
                dataset.id,
                db=db,
                current_user=SimpleNamespace(id=10, username="owner", role="user", org_id=2),
            )

            self.assertEqual(structured["semantic_model"]["dimensions"][0]["label"], "区域")
            self.assertEqual(structured["semantic_model"]["metrics"][0]["label"], "平均销售额")
            self.assertEqual(structured["semantic_model"]["metrics"][0]["aggregation"], "avg")
        finally:
            os.unlink(source_path)

    def test_semantic_query_executes_dataset_scoped_metric(self):
        from app.api.query import semantic_query
        from app.schemas.query import SemanticQueryRequest

        source_path = self._source_database()
        try:
            db, dataset = self._dataset_fixture(source_path)
            response = semantic_query(
                SemanticQueryRequest(
                    dataset_id=dataset.id,
                    dimensions=["region"],
                    metrics=["total_amount"],
                    limit=20,
                ),
                db=db,
                current_user=SimpleNamespace(id=99, username="analyst", role="user", org_id=2),
            )

            self.assertEqual(response["columns"], ["region", "total_amount"])
            self.assertEqual(response["labels"], {"region": "区域", "total_amount": "销售额"})
            self.assertEqual(
                response["rows"],
                [
                    {"region": "East", "total_amount": 100},
                    {"region": "West", "total_amount": 80},
                ],
            )
            self.assertIn("GROUP BY", response["sql_query"])
            self.assertIn("ORDER BY total_amount DESC", response["sql_query"])
            self.assertIn("sales.status", response["sql_query"])
        finally:
            os.unlink(source_path)

    def _source_database_with_time(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        source_engine = create_engine(f"sqlite:///{path}")
        with source_engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE time_sales (
                      region TEXT NOT NULL,
                      order_date TEXT NOT NULL,
                      amount INTEGER NOT NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO time_sales (region, order_date, amount)
                    VALUES
                      ('East', '2016-12-05', 100),
                      ('East', '2017-02-10', 80),
                      ('West', '2017-06-15', 50),
                      ('West', '2018-01-20', 30)
                    """
                )
            )
        source_engine.dispose()
        return path

    def _time_dataset_fixture(self, source_path: str):
        from app.models.audit_log import AuditLog
        from app.models.dataset import Dataset
        from app.models.datasource import DataSource

        db = self._db([DataSource.__table__, Dataset.__table__, AuditLog.__table__])
        datasource = DataSource(
            name="Time Sales DB",
            slug="time-sales-db",
            source_type="database",
            database_url=f"sqlite:///{source_path}",
            metadata_prompt="",
            org_id=2,
        )
        db.add(datasource)
        db.flush()
        dataset = Dataset(
            name="Time Sales Dataset",
            datasource_id=datasource.id,
            fields_json={
                "table": "time_sales",
                "fields": ["time_sales.region", "time_sales.order_date", "time_sales.amount"],
            },
            filters_json={},
            semantic_model_json={
                "dimensions": [
                    {"id": "region", "field": "time_sales.region", "label": "区域"},
                ],
                "metrics": [
                    {"id": "total_amount", "field": "time_sales.amount", "label": "销售额", "aggregation": "sum"},
                ],
                "time_dimensions": [
                    {"id": "order_date", "field": "time_sales.order_date", "label": "下单日期", "granularity": "day"},
                ],
                "synonyms": [],
            },
            status="published",
            visibility="org",
            org_id=2,
            owner_id=10,
        )
        db.add(dataset)
        db.commit()
        db.refresh(dataset)
        return db, dataset

    def _source_database_with_orders(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        source_engine = create_engine(f"sqlite:///{path}")
        with source_engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE orders (
                      id INTEGER NOT NULL,
                      customer_id TEXT NOT NULL,
                      order_date TEXT NOT NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE customers (
                      id TEXT NOT NULL,
                      region TEXT NOT NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE order_payments (
                      order_id INTEGER NOT NULL,
                      amount INTEGER NOT NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO orders (id, customer_id, order_date)
                    VALUES
                      (1, 'c1', '2017-03-01'),
                      (2, 'c2', '2017-05-02'),
                      (3, 'c1', '2018-01-10')
                    """
                )
            )
            conn.execute(text("INSERT INTO customers (id, region) VALUES ('c1', 'East'), ('c2', 'West')"))
            conn.execute(
                text("INSERT INTO order_payments (order_id, amount) VALUES (1, 50), (2, 30), (3, 20)")
            )
        source_engine.dispose()
        return path

    def _order_dataset_fixture(self, source_path: str):
        from app.models.audit_log import AuditLog
        from app.models.dataset import Dataset
        from app.models.datasource import DataSource

        db = self._db([DataSource.__table__, Dataset.__table__, AuditLog.__table__])
        datasource = DataSource(
            name="Orders DB",
            slug=f"orders-db-{os.path.basename(source_path)}",
            source_type="database",
            database_url=f"sqlite:///{source_path}",
            metadata_prompt="",
            org_id=2,
        )
        db.add(datasource)
        db.flush()
        dataset = Dataset(
            name="Orders Semantic Dataset",
            datasource_id=datasource.id,
            fields_json={
                "table": "orders",
                "fields": ["orders.id", "orders.customer_id", "orders.order_date"],
            },
            filters_json={},
            joins_json={
                "joins": [
                    {
                        "type": "LEFT JOIN",
                        "right": "customers",
                        "on": "orders.customer_id = customers.id",
                    },
                    {
                        "type": "LEFT JOIN",
                        "right": "order_payments",
                        "on": "orders.id = order_payments.order_id",
                    },
                ]
            },
            semantic_model_json={
                "dimensions": [
                    {"id": "region", "field": "customers.region", "label": "区域"},
                ],
                "metrics": [
                    {"id": "total_amount", "field": "order_payments.amount", "label": "销售额", "aggregation": "sum"},
                ],
                "time_dimensions": [
                    {"id": "order_date", "field": "orders.order_date", "label": "下单日期", "granularity": "day"},
                ],
                "synonyms": [],
            },
            status="published",
            visibility="org",
            org_id=2,
            owner_id=10,
        )
        db.add(dataset)
        db.commit()
        db.refresh(dataset)
        return db, dataset

    def test_semantic_request_filters_accept_strings_and_dicts(self):
        """filters 同时接受字符串与对象（回归：此前 schema 限定 dict 导致字符串过滤 422）。"""
        from app.api.query import semantic_query
        from app.schemas.query import SemanticQueryRequest

        source_path = self._source_database()
        try:
            db, dataset = self._dataset_fixture(source_path)
            user = SimpleNamespace(id=99, username="analyst", role="user", org_id=2)

            response = semantic_query(
                SemanticQueryRequest(
                    dataset_id=dataset.id,
                    dimensions=["region"],
                    metrics=["total_amount"],
                    filters=["sales.status = paid", "sales.amount >= 50"],
                    limit=20,
                ),
                db=db,
                current_user=user,
            )
            self.assertEqual(
                response["rows"],
                [{"region": "East", "total_amount": 100}, {"region": "West", "total_amount": 80}],
            )
            self.assertIn("sales.amount >= :semantic_filter_2", response["sql_query"])

            dict_response = semantic_query(
                SemanticQueryRequest(
                    dataset_id=dataset.id,
                    dimensions=["region"],
                    metrics=["total_amount"],
                    filters=[{"field": "sales.amount", "op": ">=", "value": 50}],
                    limit=20,
                ),
                db=db,
                current_user=user,
            )
            self.assertEqual(
                dict_response["rows"],
                [{"region": "East", "total_amount": 100}, {"region": "West", "total_amount": 80}],
            )
        finally:
            os.unlink(source_path)

    def test_semantic_query_time_granularity_and_case_insensitive_dimension(self):
        """时间维度支持 _year/_month 粒度聚合，且维度 ID 大小写不敏感回退。"""
        from app.api.query import semantic_query
        from app.schemas.query import SemanticQueryRequest

        source_path = self._source_database_with_time()
        try:
            db, dataset = self._time_dataset_fixture(source_path)
            user = SimpleNamespace(id=99, username="analyst", role="user", org_id=2)

            response = semantic_query(
                SemanticQueryRequest(
                    dataset_id=dataset.id,
                    dimensions=["order_date_year"],
                    metrics=["total_amount"],
                    limit=20,
                ),
                db=db,
                current_user=user,
            )
            self.assertEqual(response["columns"], ["order_date_year", "total_amount"])
            self.assertEqual(
                response["rows"],
                [
                    {"order_date_year": "2017", "total_amount": 130},
                    {"order_date_year": "2016", "total_amount": 100},
                    {"order_date_year": "2018", "total_amount": 30},
                ],
            )
            self.assertIn("strftime('%Y', time_sales.order_date)", response["sql_query"])

            # 大小写变体应回退命中派生维度 ID
            case_response = semantic_query(
                SemanticQueryRequest(
                    dataset_id=dataset.id,
                    dimensions=["ORDER_DATE_YEAR"],
                    metrics=["total_amount"],
                    limit=20,
                ),
                db=db,
                current_user=user,
            )
            self.assertEqual(case_response["columns"], ["order_date_year", "total_amount"])
            self.assertEqual(len(case_response["rows"]), 3)
        finally:
            os.unlink(source_path)

    def test_semantic_query_time_range_filter_limits_rows(self):
        """字符串过滤器按 2017-01-01 ~ 2017-12-31 限定时间范围并返回精确数据。"""
        from app.api.query import semantic_query
        from app.schemas.query import SemanticQueryRequest

        source_path = self._source_database_with_time()
        try:
            db, dataset = self._time_dataset_fixture(source_path)
            response = semantic_query(
                SemanticQueryRequest(
                    dataset_id=dataset.id,
                    dimensions=["order_date_month"],
                    metrics=["total_amount"],
                    filters=["order_date >= 2017-01-01", "order_date < 2018-01-01"],
                    limit=20,
                ),
                db=db,
                current_user=SimpleNamespace(id=99, username="analyst", role="user", org_id=2),
            )
            self.assertIn("time_sales.order_date >= :semantic_filter_0", response["sql_query"])
            self.assertIn("time_sales.order_date < :semantic_filter_1", response["sql_query"])
            self.assertEqual(
                response["rows"],
                [
                    {"order_date_month": "2017-02", "total_amount": 80},
                    {"order_date_month": "2017-06", "total_amount": 50},
                ],
            )
        finally:
            os.unlink(source_path)

    def test_semantic_query_joins_linked_tables(self):
        """跨表（orders × customers × order_payments）按客户区域与年份取金额。"""
        from app.api.query import semantic_query
        from app.schemas.query import SemanticQueryRequest

        source_path = self._source_database_with_orders()
        try:
            db, dataset = self._order_dataset_fixture(source_path)
            user = SimpleNamespace(id=99, username="analyst", role="user", org_id=2)

            response = semantic_query(
                SemanticQueryRequest(
                    dataset_id=dataset.id,
                    dimensions=["region"],
                    metrics=["total_amount"],
                    filters=["orders.order_date >= 2017-01-01", "orders.order_date < 2018-01-01"],
                    limit=20,
                ),
                db=db,
                current_user=user,
            )
            self.assertEqual(
                response["rows"],
                [{"region": "East", "total_amount": 50}, {"region": "West", "total_amount": 30}],
            )
            self.assertIn("LEFT JOIN customers ON orders.customer_id = customers.id", response["sql_query"])
            self.assertIn("LEFT JOIN order_payments ON orders.id = order_payments.order_id", response["sql_query"])
            self.assertIn("FROM orders", response["sql_query"])

            grouped = semantic_query(
                SemanticQueryRequest(
                    dataset_id=dataset.id,
                    dimensions=["region", "order_date_year"],
                    metrics=["total_amount"],
                    limit=20,
                ),
                db=db,
                current_user=user,
            )
            self.assertEqual(
                grouped["rows"],
                [
                    {"region": "East", "order_date_year": "2017", "total_amount": 50},
                    {"region": "West", "order_date_year": "2017", "total_amount": 30},
                    {"region": "East", "order_date_year": "2018", "total_amount": 20},
                ],
            )
        finally:
            os.unlink(source_path)

    def test_semantic_query_rejects_unlinked_table_reference(self):
        """引用未关联表字段时报清晰错误，而不是生成非法 SQL。"""
        from app.api.query import semantic_query
        from app.schemas.query import SemanticQueryRequest

        source_path = self._source_database_with_orders()
        try:
            db, dataset = self._order_dataset_fixture(source_path)
            dataset.joins_json = None
            db.commit()
            with self.assertRaises(HTTPException) as exc:
                semantic_query(
                    SemanticQueryRequest(
                        dataset_id=dataset.id,
                        dimensions=["region"],
                        metrics=["total_amount"],
                        limit=20,
                    ),
                    db=db,
                    current_user=SimpleNamespace(id=99, username="analyst", role="user", org_id=2),
                )
            self.assertEqual(exc.exception.status_code, 400)
            self.assertIn("未关联", exc.exception.detail)
        finally:
            os.unlink(source_path)


if __name__ == "__main__":
    unittest.main()
