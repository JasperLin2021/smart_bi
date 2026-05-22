import os
import tempfile
import unittest
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


class DataSourceCreationTests(unittest.TestCase):
    def _db(self):
        from app.db.base import Base

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        return sessionmaker(bind=engine)()

    def test_create_datasource_auto_detects_schema_and_metadata_prompt(self):
        from app.api.datasource import create_datasource
        from app.models.datasource import DataSource
        from app.models.user import User
        from app.schemas.datasource import DataSourceCreate

        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            source_engine = create_engine(f"sqlite:///{path}")
            with source_engine.begin() as conn:
                conn.execute(text("CREATE TABLE orders (id INTEGER PRIMARY KEY, region TEXT, amount INTEGER)"))
            source_engine.dispose()

            db = self._db()
            current_user = User(id=1, username="admin", hashed_password="x", role="super_admin")
            db.add(current_user)
            db.commit()

            created = create_datasource(
                DataSourceCreate(
                    name="订单数据源",
                    slug="orders-ds",
                    database_url=f"sqlite:///{path}",
                    source_type="database",
                    metadata_prompt="",
                ),
                db=db,
                current_user=current_user,
            )

            self.assertEqual(created["schema_metadata"]["tables"][0]["name"], "orders")
            self.assertIn("region", [col["name"] for col in created["schema_metadata"]["tables"][0]["columns"]])
            self.assertIn("orders 表", created["metadata_prompt"])

            saved = db.query(DataSource).filter(DataSource.id == created["id"]).one()
            self.assertIsNotNone(saved.schema_metadata)
            self.assertIn("orders 表", saved.metadata_prompt)
        finally:
            os.unlink(path)

    def test_create_datasource_schedules_recommend_questions_without_blocking(self):
        from app.api.datasource import create_datasource
        from app.models.datasource import DataSource
        from app.models.user import User
        from app.schemas.datasource import DataSourceCreate

        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            source_engine = create_engine(f"sqlite:///{path}")
            with source_engine.begin() as conn:
                conn.execute(text("CREATE TABLE alarms (id INTEGER PRIMARY KEY, alarm_id TEXT, occurred_at TEXT)"))
            source_engine.dispose()

            db = self._db()
            current_user = User(id=1, username="admin", hashed_password="x", role="super_admin")
            db.add(current_user)
            db.commit()

            class FakeBackgroundTasks:
                def __init__(self):
                    self.tasks = []

                def add_task(self, func, *args, **kwargs):
                    self.tasks.append((func, args, kwargs))

            background_tasks = FakeBackgroundTasks()
            with patch(
                "app.api.datasource.generate_recommend_questions",
                new=AsyncMock(side_effect=AssertionError("recommend question generation should run after response")),
            ) as mocked:
                created = create_datasource(
                    DataSourceCreate(
                        name="报警数据源",
                        slug="alarms-ds",
                        database_url=f"sqlite:///{path}",
                        source_type="database",
                        metadata_prompt="",
                        recommend_questions=None,
                    ),
                    db=db,
                    current_user=current_user,
                    background_tasks=background_tasks,
                )

            mocked.assert_not_awaited()
            self.assertIsNone(created["recommend_questions"])
            self.assertEqual(len(background_tasks.tasks), 1)
            self.assertEqual(background_tasks.tasks[0][1][0], created["id"])

            saved = db.query(DataSource).filter(DataSource.id == created["id"]).one()
            self.assertIsNone(saved.recommend_questions)
        finally:
            os.unlink(path)

    def test_database_preview_sql_uses_sql_server_top_syntax(self):
        from app.api.datasource import _database_preview_sql

        engine = SimpleNamespace(dialect=SimpleNamespace(name="mssql"))

        self.assertEqual(
            _database_preview_sql(engine, "[agentic_orders]", 2),
            "SELECT TOP 2 * FROM [agentic_orders]",
        )

    def test_detect_database_schema_infers_relationships_without_foreign_keys(self):
        from app.core.schema_detector import detect_database_schema

        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            source_engine = create_engine(f"sqlite:///{path}")
            with source_engine.begin() as conn:
                conn.execute(text("CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT)"))
                conn.execute(text("CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER, amount INTEGER)"))
                conn.execute(text("INSERT INTO customers (id, name) VALUES (1, 'A'), (2, 'B')"))
                conn.execute(text("INSERT INTO orders (customer_id, amount) VALUES (1, 10), (1, 20), (2, 30)"))
            source_engine.dispose()

            schema = detect_database_schema(f"sqlite:///{path}")

            relation = next(
                (
                    item for item in schema.relationships
                    if item.from_table == "orders"
                    and item.from_column == "customer_id"
                    and item.to_table == "customers"
                    and item.to_column == "id"
                ),
                None,
            )
            self.assertIsNotNone(relation)
            self.assertEqual(relation.status, "inferred")
            self.assertGreaterEqual(relation.confidence or 0, 0.8)
            self.assertTrue(any("命名" in item for item in relation.evidence))
            self.assertTrue(any("覆盖率" in item for item in relation.evidence))
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
