import json
import unittest
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class AuditLogTests(unittest.TestCase):
    def _db(self):
        from app.db.base_class import Base
        from app.models.audit_log import AuditLog
        from app.models.organization import Organization  # noqa: F401

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine, tables=[AuditLog.__table__])
        return sessionmaker(bind=engine)()

    def test_record_audit_log_persists_actor_resource_and_detail(self):
        from app.core.audit import record_audit_log
        from app.models.audit_log import AuditLog

        db = self._db()
        actor = SimpleNamespace(id=10, username="alice", role="org_admin", org_id=2)

        log = record_audit_log(
            db,
            actor=actor,
            action="datasource.create",
            resource_type="datasource",
            resource_id=7,
            resource_name="Mock PGSQL",
            status="success",
            message="数据源已创建",
            detail={"slug": "mock-pgsql"},
        )

        stored = db.query(AuditLog).one()
        self.assertEqual(log.id, stored.id)
        self.assertEqual(stored.actor_user_id, 10)
        self.assertEqual(stored.actor_username, "alice")
        self.assertEqual(stored.actor_role, "org_admin")
        self.assertEqual(stored.org_id, 2)
        self.assertEqual(stored.action, "datasource.create")
        self.assertEqual(stored.resource_type, "datasource")
        self.assertEqual(stored.resource_id, "7")
        self.assertEqual(stored.resource_name, "Mock PGSQL")
        self.assertEqual(stored.status, "success")
        self.assertEqual(stored.message, "数据源已创建")
        self.assertEqual(json.loads(stored.detail_json), {"slug": "mock-pgsql"})

    def test_org_admin_lists_only_same_org_audit_logs(self):
        from app.api.audit import list_audit_logs
        from app.models.audit_log import AuditLog

        db = self._db()
        db.add_all(
            [
                AuditLog(action="datasource.create", resource_type="datasource", org_id=2, actor_username="same"),
                AuditLog(action="datasource.delete", resource_type="datasource", org_id=1, actor_username="other"),
                AuditLog(action="dashboard.publish", resource_type="dashboard", org_id=2, actor_username="same"),
            ]
        )
        db.commit()

        result = list_audit_logs(
            db=db,
            current_user=SimpleNamespace(id=11, username="admin", role="org_admin", org_id=2),
        )

        self.assertEqual(result.total, 2)
        self.assertEqual([item.actor_username for item in result.items], ["same", "same"])

    def test_super_admin_lists_all_audit_logs(self):
        from app.api.audit import list_audit_logs
        from app.models.audit_log import AuditLog

        db = self._db()
        db.add_all(
            [
                AuditLog(action="datasource.create", resource_type="datasource", org_id=2),
                AuditLog(action="datasource.delete", resource_type="datasource", org_id=1),
            ]
        )
        db.commit()

        result = list_audit_logs(
            db=db,
            current_user=SimpleNamespace(id=1, username="root", role="super_admin", org_id=None),
        )

        self.assertEqual(result.total, 2)


if __name__ == "__main__":
    unittest.main()
