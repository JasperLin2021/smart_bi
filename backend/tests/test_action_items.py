import unittest
from datetime import date
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class ActionItemTests(unittest.TestCase):
    def _db(self):
        from app.db.base_class import Base
        from app.models.action_item import ActionItem
        from app.models.audit_log import AuditLog
        from app.models.dashboard_config import Dashboard
        from app.models.dataset import Dataset
        from app.models.datasource import DataSource
        from app.models.metric import Metric
        from app.models.organization import Organization
        from app.models.user import User

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(
            bind=engine,
            tables=[
                Organization.__table__,
                User.__table__,
                DataSource.__table__,
                Metric.__table__,
                Dataset.__table__,
                Dashboard.__table__,
                ActionItem.__table__,
                AuditLog.__table__,
            ],
        )
        return sessionmaker(bind=engine)()

    def _seed_links(self, db, org_id: int = 2):
        from app.models.dashboard_config import Dashboard
        from app.models.dataset import Dataset
        from app.models.datasource import DataSource
        from app.models.metric import Metric

        datasource = DataSource(
            name=f"Sales {org_id}",
            slug=f"sales-{org_id}",
            database_url="sqlite:///:memory:",
            metadata_prompt="",
            org_id=org_id,
        )
        db.add(datasource)
        db.commit()
        db.refresh(datasource)

        metric = Metric(
            datasource_id=datasource.id,
            name=f"销售额-{org_id}",
            definition="统计销售额",
            formula="SUM(amount)",
        )
        dataset = Dataset(name=f"销售数据集-{org_id}", datasource_id=datasource.id, org_id=org_id, owner_id=10)
        dashboard = Dashboard(title=f"经营看板-{org_id}", org_id=org_id, owner_id=10)
        db.add_all([metric, dataset, dashboard])
        db.commit()
        db.refresh(metric)
        db.refresh(dataset)
        db.refresh(dashboard)
        return datasource, metric, dataset, dashboard

    def test_create_action_item_from_query_result_tracks_owner_links_and_audit(self):
        from app.api.action_items import create_action_item
        from app.models.audit_log import AuditLog
        from app.schemas.action_item import ActionItemCreate

        db = self._db()
        _, metric, dataset, dashboard = self._seed_links(db)
        user = SimpleNamespace(id=20, username="analyst", role="user", org_id=2)

        item = create_action_item(
            ActionItemCreate(
                title="跟进华东销售额下滑",
                description="本周销售额低于目标，需要确认渠道原因。",
                source_type="query",
                source_id="88",
                source_payload={"question": "本周各区域销售额", "summary": "华东下降 12%"},
                priority="high",
                due_date=date(2026, 5, 8),
                linked_metric_id=metric.id,
                linked_dataset_id=dataset.id,
                linked_dashboard_id=dashboard.id,
            ),
            db=db,
            current_user=user,
        )

        self.assertEqual(item.org_id, 2)
        self.assertEqual(item.created_by, 20)
        self.assertEqual(item.owner_id, 20)
        self.assertEqual(item.status, "open")
        self.assertEqual(item.source_type, "query")
        self.assertEqual(item.linked_metric_id, metric.id)
        self.assertEqual(item.linked_dataset_id, dataset.id)
        self.assertEqual(item.linked_dashboard_id, dashboard.id)
        self.assertEqual(item.source_payload["summary"], "华东下降 12%")

        audit = db.query(AuditLog).filter(AuditLog.action == "action_item.create").one()
        self.assertEqual(audit.org_id, 2)
        self.assertEqual(audit.resource_name, "跟进华东销售额下滑")

    def test_visibility_and_outcome_update_follow_org_and_assignment_scope(self):
        from app.api.action_items import create_action_item, list_action_items, update_action_item
        from app.schemas.action_item import ActionItemCreate, ActionItemUpdate

        db = self._db()
        self._seed_links(db)
        owner = SimpleNamespace(id=20, username="owner", role="user", org_id=2)
        outsider = SimpleNamespace(id=21, username="other", role="user", org_id=2)
        admin = SimpleNamespace(id=10, username="admin", role="org_admin", org_id=2)

        item = create_action_item(
            ActionItemCreate(title="处理异常工单", owner_id=owner.id, source_type="alert", source_id="5"),
            db=db,
            current_user=admin,
        )

        owner_items = list_action_items(db=db, current_user=owner)["items"]
        outsider_items = list_action_items(db=db, current_user=outsider)["items"]
        admin_items = list_action_items(db=db, current_user=admin)["items"]
        self.assertEqual([action.id for action in owner_items], [item.id])
        self.assertEqual(outsider_items, [])
        self.assertEqual([action.id for action in admin_items], [item.id])

        updated = update_action_item(
            item.id,
            ActionItemUpdate(status="done", outcome="已联系区域负责人，调整下周投放。"),
            db=db,
            current_user=owner,
        )
        self.assertEqual(updated.status, "done")
        self.assertEqual(updated.outcome, "已联系区域负责人，调整下周投放。")
        self.assertIsNotNone(updated.closed_at)

        with self.assertRaises(HTTPException):
            update_action_item(
                item.id,
                ActionItemUpdate(status="cancelled"),
                db=db,
                current_user=outsider,
            )

    def test_rejects_cross_org_linked_resources(self):
        from app.api.action_items import create_action_item
        from app.schemas.action_item import ActionItemCreate

        db = self._db()
        self._seed_links(db, org_id=2)
        _, other_metric, _, _ = self._seed_links(db, org_id=3)
        user = SimpleNamespace(id=20, username="analyst", role="user", org_id=2)

        with self.assertRaises(HTTPException) as ctx:
            create_action_item(
                ActionItemCreate(title="跨组织指标跟进", linked_metric_id=other_metric.id),
                db=db,
                current_user=user,
            )

        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
