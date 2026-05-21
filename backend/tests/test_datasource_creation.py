import os
import tempfile
import unittest
import json
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

    def test_create_datasource_generates_three_recommend_questions_when_missing(self):
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

            generated_questions = [
                "最近 7 天报警次数趋势",
                "各报警码发生次数 Top10",
                "按日期统计报警发生次数",
                "查看报警设备分布",
            ]
            expected_questions = generated_questions[:3]
            with patch(
                "app.api.datasource.generate_recommend_questions",
                new=AsyncMock(return_value=generated_questions),
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
                )

            mocked.assert_awaited_once()
            self.assertEqual(mocked.await_args.kwargs["limit"], 3)
            self.assertEqual(created["recommend_questions"], expected_questions)

            saved = db.query(DataSource).filter(DataSource.id == created["id"]).one()
            self.assertEqual(json.loads(saved.recommend_questions), expected_questions)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
