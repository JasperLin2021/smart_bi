import unittest
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class _FakeWechatClient:
    def __init__(self, should_fail=False):
        self.should_fail = should_fail
        self.sent = []

    def get_access_token(self):
        return "token-1"

    def send_textcard(self, access_token, to_user, title, content, url=None):
        if self.should_fail:
            raise ValueError("send failed")
        self.sent.append((access_token, to_user, title, content, url))


class MessageDispatcherTests(unittest.TestCase):
    def _db(self):
        from app.db.base_class import Base
        from app.models.integration import (
            ExternalIdentity,
            ExternalOrgBinding,
            ExternalPermissionMapping,
            IntegrationConfig,
            MessageDelivery,
        )
        from app.models.organization import Organization
        from app.models.user import User

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(
            bind=engine,
            tables=[
                Organization.__table__,
                User.__table__,
                IntegrationConfig.__table__,
                ExternalOrgBinding.__table__,
                ExternalPermissionMapping.__table__,
                ExternalIdentity.__table__,
                MessageDelivery.__table__,
            ],
        )
        db = sessionmaker(bind=engine)()
        db.add(Organization(id=2, name="嘉盛半导体", slug="carsem"))
        db.add(User(id=10, username="owner", hashed_password="!", role="user", org_id=2))
        db.add(
            IntegrationConfig(
                provider="wechat_work",
                name="企业微信",
                enabled=True,
                corp_id="corp-1",
                agent_id="1000002",
                app_secret="secret-1",
                callback_url="https://bi.example.com/api/auth/wechat-work/callback",
            )
        )
        db.commit()
        return db

    def test_dispatch_success_writes_success_delivery(self):
        from app.core.message_dispatcher import MessageEvent, dispatch_message_event
        from app.models.integration import ExternalIdentity, MessageDelivery

        db = self._db()
        db.add(
            ExternalIdentity(
                provider="wechat_work",
                external_corp_id="corp-1",
                external_user_id="zhangsan",
                user_id=10,
            )
        )
        db.commit()
        fake_client = _FakeWechatClient()

        deliveries = dispatch_message_event(
            db,
            MessageEvent(
                event_type="action_item.assigned",
                org_id=2,
                recipient_user_ids=[10],
                title="行动项提醒",
                content="请处理异常工单",
                link_url="/action-items",
            ),
            client_factory=lambda config: fake_client,
        )

        self.assertEqual(len(deliveries), 1)
        delivery = db.query(MessageDelivery).one()
        self.assertEqual(delivery.status, "success")
        self.assertEqual(delivery.recipient_external_user_id, "zhangsan")
        self.assertIsNotNone(delivery.sent_at)
        self.assertEqual(fake_client.sent[0][1], "zhangsan")

    def test_missing_external_identity_is_recorded_as_failed(self):
        from app.core.message_dispatcher import MessageEvent, dispatch_message_event
        from app.models.integration import MessageDelivery

        db = self._db()
        deliveries = dispatch_message_event(
            db,
            MessageEvent(
                event_type="dashboard.shared",
                org_id=2,
                recipient_user_ids=[10],
                title="看板分享",
                content="经营看板已分享给你",
            ),
            client_factory=lambda config: _FakeWechatClient(),
        )

        self.assertEqual(len(deliveries), 1)
        delivery = db.query(MessageDelivery).one()
        self.assertEqual(delivery.status, "failed")
        self.assertIn("未绑定企业微信身份", delivery.error_message)

    def test_client_error_is_recorded_as_failed_without_raising(self):
        from app.core.message_dispatcher import MessageEvent, dispatch_message_event
        from app.models.integration import ExternalIdentity, MessageDelivery

        db = self._db()
        db.add(
            ExternalIdentity(
                provider="wechat_work",
                external_corp_id="corp-1",
                external_user_id="zhangsan",
                user_id=10,
            )
        )
        db.commit()

        dispatch_message_event(
            db,
            MessageEvent(
                event_type="scheduled_report.generated",
                org_id=2,
                recipient_user_ids=[10],
                title="定时报告",
                content="日报已生成",
            ),
            client_factory=lambda config: _FakeWechatClient(should_fail=True),
        )

        delivery = db.query(MessageDelivery).one()
        self.assertEqual(delivery.status, "failed")
        self.assertIn("send failed", delivery.error_message)

    def test_approval_requested_event_can_be_dispatched(self):
        from app.core.message_dispatcher import MessageEvent, dispatch_message_event
        from app.models.integration import ExternalIdentity, MessageDelivery

        db = self._db()
        db.add(
            ExternalIdentity(
                provider="wechat_work",
                external_corp_id="corp-1",
                external_user_id="zhangsan",
                user_id=10,
            )
        )
        db.commit()

        dispatch_message_event(
            db,
            MessageEvent(
                event_type="approval.requested",
                org_id=2,
                recipient_user_ids=[10],
                title="审批提醒",
                content="有一项审批需要处理",
            ),
            client_factory=lambda config: _FakeWechatClient(),
        )

        delivery = db.query(MessageDelivery).one()
        self.assertEqual(delivery.event_type, "approval.requested")
        self.assertEqual(delivery.status, "success")


class BusinessEventHookTests(unittest.TestCase):
    def _db(self, tables):
        from app.db.base_class import Base

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine, tables=tables)
        return sessionmaker(bind=engine)()

    def test_action_item_create_and_status_update_emit_message_events(self):
        from app.api.action_items import create_action_item, update_action_item
        from app.models.action_item import ActionItem
        from app.models.audit_log import AuditLog
        from app.schemas.action_item import ActionItemCreate, ActionItemUpdate

        db = self._db([ActionItem.__table__, AuditLog.__table__])
        admin = SimpleNamespace(id=10, username="admin", role="org_admin", org_id=2)

        with patch("app.api.action_items.dispatch_message_event") as dispatch:
            item = create_action_item(
                ActionItemCreate(title="处理异常工单", owner_id=20),
                db=db,
                current_user=admin,
            )

        assigned_event = dispatch.call_args.args[1]
        self.assertEqual(assigned_event.event_type, "action_item.assigned")
        self.assertEqual(assigned_event.recipient_user_ids, [20])
        self.assertEqual(assigned_event.org_id, 2)

        with patch("app.api.action_items.dispatch_message_event") as dispatch:
            update_action_item(
                item.id,
                ActionItemUpdate(status="done"),
                db=db,
                current_user=SimpleNamespace(id=20, username="owner", role="user", org_id=2),
            )

        status_event = dispatch.call_args.args[1]
        self.assertEqual(status_event.event_type, "action_item.status_changed")
        self.assertEqual(status_event.recipient_user_ids, [20, 10])

    def test_dashboard_comment_emits_message_to_owner_and_shared_users_except_author(self):
        from app.api.comments import create_comment
        from app.models.dashboard_comment import DashboardComment
        from app.models.dashboard_config import Dashboard
        from app.schemas.integration import MessageDeliveryOut  # noqa: F401

        db = self._db([Dashboard.__table__, DashboardComment.__table__])
        dashboard = Dashboard(id=5, title="经营看板", org_id=2, owner_id=10, shared_user_ids=[11, 12])
        db.add(dashboard)
        db.commit()

        with patch("app.api.comments.dispatch_message_event") as dispatch:
            create_comment(
                5,
                SimpleNamespace(content="请看这个指标变化"),
                db=db,
                current_user=SimpleNamespace(id=11, username="reviewer", role="user", org_id=2),
            )

        event = dispatch.call_args.args[1]
        self.assertEqual(event.event_type, "dashboard.comment.created")
        self.assertEqual(event.recipient_user_ids, [10, 12])

    def test_dashboard_share_emits_message_to_shared_users(self):
        from app.api.dashboards import share_dashboard
        from app.models.audit_log import AuditLog
        from app.models.catalog import DataAsset
        from app.models.dashboard_config import Dashboard
        from app.schemas.dashboard_center import DashboardShareUpdate

        db = self._db([Dashboard.__table__, DataAsset.__table__, AuditLog.__table__])
        db.add(Dashboard(id=6, title="经营看板", org_id=2, owner_id=10))
        db.commit()

        with patch("app.api.dashboards.dispatch_message_event") as dispatch:
            share_dashboard(
                6,
                DashboardShareUpdate(is_public=False, shared_user_ids=[11, 12]),
                db=db,
                current_user=SimpleNamespace(id=10, username="owner", role="user", org_id=2),
            )

        event = dispatch.call_args.args[1]
        self.assertEqual(event.event_type, "dashboard.shared")
        self.assertEqual(event.recipient_user_ids, [11, 12])

    def test_alert_and_report_modules_use_dispatcher(self):
        import inspect
        from app.core import alert_evaluator, alert_scheduler

        alert_source = inspect.getsource(alert_evaluator)
        report_source = inspect.getsource(alert_scheduler)

        self.assertIn("dispatch_message_event", alert_source)
        self.assertIn("alert.triggered", alert_source)
        self.assertIn("dispatch_message_event", report_source)
        self.assertIn("scheduled_report.generated", report_source)
