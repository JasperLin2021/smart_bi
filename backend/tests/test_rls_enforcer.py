import unittest
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class RLSEnforcerTests(unittest.TestCase):
    def test_missing_rls_table_is_treated_as_no_rules(self):
        from app.db.base_class import Base
        from app.models.datasource import DataSource
        from app.models.organization import Organization  # noqa: F401
        from app.core.rls_enforcer import get_rls_clauses

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine, tables=[DataSource.__table__])
        db = sessionmaker(bind=engine)()

        clauses = get_rls_clauses(
            db,
            datasource_id=1,
            user=SimpleNamespace(id=10, role="user", org_id=2),
        )

        self.assertEqual(clauses, [])


if __name__ == "__main__":
    unittest.main()
