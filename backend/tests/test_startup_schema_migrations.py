import os
import tempfile
import unittest

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


class StartupSchemaMigrationTests(unittest.TestCase):
    def test_ensure_column_adds_missing_sqlite_column(self):
        from app.main import _ensure_column

        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            engine = create_engine(f"sqlite:///{path}")
            with engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        CREATE TABLE query_history (
                          id INTEGER PRIMARY KEY,
                          question TEXT NOT NULL
                        )
                        """
                    )
                )

            _ensure_column(engine, "query_history", "parent_history_id INTEGER")

            with engine.connect() as conn:
                columns = {
                    row[1]
                    for row in conn.execute(text("PRAGMA table_info(query_history)")).fetchall()
                }

            self.assertIn("parent_history_id", columns)
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_startup_adds_permission_columns_for_existing_users(self):
        import app.main as main_module

        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            engine = create_engine(f"sqlite:///{path}")
            with engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        CREATE TABLE users (
                          id INTEGER PRIMARY KEY,
                          username VARCHAR(255) NOT NULL,
                          hashed_password VARCHAR(255) NOT NULL,
                          role VARCHAR(50) NOT NULL,
                          org_id INTEGER NULL
                        )
                        """
                    )
                )
                conn.execute(
                    text(
                        """
                        INSERT INTO users (username, hashed_password, role, org_id)
                        VALUES ('admin', 'hashed', 'super_admin', NULL)
                        """
                    )
                )

            original_engine = main_module.engine
            original_session_local = main_module.SessionLocal
            original_init_cache = main_module.init_cache
            try:
                main_module.engine = engine
                main_module.SessionLocal = sessionmaker(bind=engine)
                main_module.init_cache = lambda: None

                main_module.startup()
            finally:
                main_module.engine = original_engine
                main_module.SessionLocal = original_session_local
                main_module.init_cache = original_init_cache

            with engine.connect() as conn:
                columns = {
                    row[1]
                    for row in conn.execute(text("PRAGMA table_info(users)")).fetchall()
                }

            self.assertIn("data_scope", columns)
            self.assertIn("permission_override_enabled", columns)
            self.assertIn("menu_permissions", columns)
            self.assertIn("action_permissions", columns)
        finally:
            if os.path.exists(path):
                os.remove(path)


if __name__ == "__main__":
    unittest.main()
