import json
import os
import tempfile
import unittest

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


class SchemaRefreshTests(unittest.TestCase):
    def _db(self):
        from app.db.base import Base

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        return sessionmaker(bind=engine)()

    def _make_datasource(self, db, path, name="订单数据源", slug="orders-ds"):
        from app.api.datasource import create_datasource
        from app.models.user import User
        from app.schemas.datasource import DataSourceCreate

        current_user = User(id=1, username="admin", hashed_password="x", role="super_admin")
        db.add(current_user)
        db.commit()
        created = create_datasource(
            DataSourceCreate(
                name=name,
                slug=slug,
                database_url=f"sqlite:///{path}",
                source_type="database",
                metadata_prompt="",
            ),
            db=db,
            current_user=current_user,
        )
        return created, current_user

    def test_merge_schema_metadata_adds_new_columns_and_keeps_descriptions(self):
        from app.core.schema_detector import merge_schema_metadata
        from app.schemas.datasource import ColumnSchema, SchemaMetadata, TableSchema

        previous = SchemaMetadata(
            tables=[
                TableSchema(
                    name="orders",
                    description="订单表",
                    columns=[
                        ColumnSchema(name="id", type="INTEGER", description="订单ID"),
                        ColumnSchema(name="region", type="VARCHAR", description="区域"),
                        ColumnSchema(name="amount", type="INTEGER", description="金额"),
                        ColumnSchema(name="legacy_col", type="VARCHAR", description="旧字段"),
                    ],
                )
            ],
            relationships=[],
        )
        fresh = SchemaMetadata(
            tables=[
                TableSchema(
                    name="orders",
                    description=None,
                    columns=[
                        ColumnSchema(name="id", type="INTEGER", description=None),
                        ColumnSchema(name="region", type="VARCHAR", description=None),
                        ColumnSchema(name="amount", type="INTEGER", description=None),
                        ColumnSchema(name="status", type="VARCHAR", description=None),
                    ],
                ),
                TableSchema(
                    name="customers",
                    description=None,
                    columns=[ColumnSchema(name="id", type="INTEGER", description=None)],
                ),
            ],
            relationships=[],
        )

        merged = merge_schema_metadata(previous, fresh)

        orders = next(table for table in merged.tables if table.name == "orders")
        by_name = {column.name: column for column in orders.columns}
        self.assertEqual(by_name["id"].description, "订单ID")
        self.assertEqual(by_name["region"].description, "区域")
        self.assertEqual(by_name["amount"].description, "金额")
        self.assertIn("status", by_name)  # 物理表新增的列被追加
        self.assertEqual(by_name["status"].description, None)
        self.assertNotIn("legacy_col", by_name)  # 物理表已删除的列被移除
        self.assertEqual(orders.description, "订单表")  # 表说明保留
        self.assertEqual([table.name for table in merged.tables], ["orders", "customers"])  # 新表被追加

    def test_merge_schema_metadata_keeps_relationships_and_appends_new(self):
        from app.core.schema_detector import merge_schema_metadata
        from app.schemas.datasource import RelationshipSchema, SchemaMetadata

        previous = SchemaMetadata(
            tables=[],
            relationships=[
                RelationshipSchema(
                    from_table="orders",
                    from_column="customer_id",
                    to_table="customers",
                    to_column="id",
                    status="ignored",
                    confidence=0.9,
                    source="manual",
                    evidence=["人工忽略"],
                )
            ],
        )
        fresh = SchemaMetadata(
            tables=[],
            relationships=[
                RelationshipSchema(
                    from_table="orders",
                    from_column="customer_id",
                    to_table="customers",
                    to_column="id",
                    status="confirmed",
                    confidence=1.0,
                    source="foreign_key",
                ),
                RelationshipSchema(
                    from_table="orders",
                    from_column="region_id",
                    to_table="regions",
                    to_column="id",
                    status="inferred",
                    confidence=0.72,
                    source="name_match",
                ),
            ],
        )

        merged = merge_schema_metadata(previous, fresh)

        kept = next(rel for rel in merged.relationships if rel.from_column == "customer_id")
        self.assertEqual(kept.status, "ignored")  # 既有关系保留原状态与证据
        self.assertEqual(kept.evidence, ["人工忽略"])
        self.assertEqual(
            {(rel.from_table, rel.from_column, rel.to_table, rel.to_column) for rel in merged.relationships},
            {("orders", "customer_id", "customers", "id"), ("orders", "region_id", "regions", "id")},
        )
        self.assertEqual(len(merged.relationships), 2)  # 去重且追加新关系

    def test_refresh_schema_endpoint_adds_new_column_and_updates_prompt(self):
        from app.api.datasource import refresh_datasource_schema
        from app.models.datasource import DataSource

        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            source_engine = create_engine(f"sqlite:///{path}")
            with source_engine.begin() as conn:
                conn.execute(text("CREATE TABLE orders (id INTEGER PRIMARY KEY, region TEXT, amount INTEGER)"))
            source_engine.dispose()

            db = self._db()
            created, current_user = self._make_datasource(db, path)

            # 模拟物理表新增字段
            source_engine = create_engine(f"sqlite:///{path}")
            with source_engine.begin() as conn:
                conn.execute(text("ALTER TABLE orders ADD COLUMN status TEXT"))
            source_engine.dispose()

            merged = refresh_datasource_schema(created["id"], db=db, current_user=current_user)

            orders = next(table for table in merged.tables if table.name == "orders")
            self.assertIn("status", [column.name for column in orders.columns])
            self.assertIn("region", [column.name for column in orders.columns])

            saved = db.query(DataSource).filter(DataSource.id == created["id"]).one()
            saved_schema = json.loads(saved.schema_metadata)
            saved_orders = next(table for table in saved_schema["tables"] if table["name"] == "orders")
            self.assertIn("status", [column["name"] for column in saved_orders["columns"]])
            self.assertIn("status", saved.metadata_prompt)
        finally:
            os.unlink(path)

    def test_refresh_schema_preserves_existing_description(self):
        from app.api.datasource import refresh_datasource_schema
        from app.models.datasource import DataSource
        from app.schemas.datasource import SchemaMetadata

        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            source_engine = create_engine(f"sqlite:///{path}")
            with source_engine.begin() as conn:
                conn.execute(text("CREATE TABLE orders (id INTEGER PRIMARY KEY, region TEXT, amount INTEGER)"))
            source_engine.dispose()

            db = self._db()
            created, current_user = self._make_datasource(db, path)

            # 模拟缓存的 AI 生成字段说明
            ds = db.query(DataSource).filter(DataSource.id == created["id"]).one()
            schema = SchemaMetadata.model_validate(json.loads(ds.schema_metadata))
            for table in schema.tables:
                for column in table.columns:
                    if column.name == "region":
                        column.description = "客户所在区域"
            ds.schema_metadata = json.dumps(schema.model_dump(), ensure_ascii=False)
            db.commit()

            # 模拟物理表新增字段
            source_engine = create_engine(f"sqlite:///{path}")
            with source_engine.begin() as conn:
                conn.execute(text("ALTER TABLE orders ADD COLUMN status TEXT"))
            source_engine.dispose()

            merged = refresh_datasource_schema(created["id"], db=db, current_user=current_user)

            orders = next(table for table in merged.tables if table.name == "orders")
            by_name = {column.name: column for column in orders.columns}
            self.assertEqual(by_name["region"].description, "客户所在区域")  # AI 说明保留
            self.assertIn("status", by_name)  # 新字段加入
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
