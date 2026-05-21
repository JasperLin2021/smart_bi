import re
import unittest
from pathlib import Path


class AlembicSchemaTests(unittest.TestCase):
    def test_baseline_creates_legacy_tables_referenced_by_later_migrations(self):
        baseline = (Path(__file__).resolve().parents[1] / "alembic" / "versions" / "20260429_0001_baseline.py").read_text()

        for table_name in ("organizations", "users", "datasources", "metrics"):
            self.assertRegex(
                baseline,
                re.compile(rf'sa\.Table\(\s*["\']{table_name}["\']', re.S),
            )

    def test_metric_dataset_binding_is_created_by_migration(self):
        versions_dir = Path(__file__).resolve().parents[1] / "alembic" / "versions"
        migration_text = "\n".join(path.read_text() for path in versions_dir.glob("*.py"))

        self.assertRegex(
            migration_text,
            re.compile(r'op\.add_column\(\s*["\']metrics["\']\s*,\s*sa\.Column\(\s*["\']dataset_id["\']', re.S),
        )
        self.assertRegex(
            migration_text,
            re.compile(r'op\.create_index\(\s*["\']ix_metrics_dataset_id["\']\s*,\s*["\']metrics["\']', re.S),
        )


if __name__ == "__main__":
    unittest.main()
