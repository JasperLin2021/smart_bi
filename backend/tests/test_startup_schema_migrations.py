import os
import tempfile
import unittest

from sqlalchemy import create_engine, text


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


if __name__ == "__main__":
    unittest.main()
