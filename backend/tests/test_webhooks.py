"""Webhook 订阅匹配与事件投递的单元测试。

覆盖：
- matching_subscriptions：按 org_id + 事件类型过滤启用的订阅
- sign_payload：HMAC-SHA256 签名与首部格式
- deliver_subscription：HTTP 投递成功/失败重试（mock httpx，不发真实请求）
- dispatch_event：同步模式下匹配的订阅数正确，无匹配时返回 0
"""
from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base  # noqa: F401 - 触发模型注册
from app.models.webhook_subscription import WebhookSubscription


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _add_subscription(db, *, name, target_url, events, org_id=1, secret=None, enabled=1):
    sub = WebhookSubscription(
        name=name,
        target_url=target_url,
        events=events,
        org_id=org_id,
        secret=secret,
        enabled=enabled,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


class _FakeResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code


class WebhookSubscriptionMatchingTests(unittest.TestCase):
    def test_matches_by_org_and_event_and_enabled(self):
        from app.core.webhook_dispatcher import matching_subscriptions

        db = _db()
        _add_subscription(db, name="同组织-订阅指标刷新", target_url="https://a.example/hook", events=["metric.refreshed"], org_id=1)
        _add_subscription(db, name="其他组织", target_url="https://b.example/hook", events=["metric.refreshed"], org_id=2)
        _add_subscription(db, name="同组织-订阅看板发布", target_url="https://c.example/hook", events=["dashboard.published"], org_id=1)
        _add_subscription(db, name="同组织-已禁用", target_url="https://d.example/hook", events=["metric.refreshed"], org_id=1, enabled=0)

        matched = matching_subscriptions(db, org_id=1, event_type="metric.refreshed")
        self.assertEqual([sub.name for sub in matched], ["同组织-订阅指标刷新"])


class WebhookSignatureTests(unittest.TestCase):
    def test_sign_payload_is_hmac_sha256_prefixed(self):
        import hmac
        import hashlib

        from app.core.webhook_dispatcher import sign_payload

        secret = "s3cret"
        body = b'{"event":"metric.refreshed"}'
        expected = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        self.assertEqual(sign_payload(secret, body), expected)

    def test_build_event_payload_shape(self):
        from app.core.webhook_dispatcher import build_event_payload

        payload = build_event_payload("metric.refreshed", {"metric_id": 7})
        self.assertEqual(payload["event"], "metric.refreshed")
        self.assertEqual(payload["data"], {"metric_id": 7})
        self.assertIn("timestamp", payload)


class WebhookDeliveryTests(unittest.TestCase):
    def test_deliver_subscription_success_returns_true(self):
        from app.core.webhook_dispatcher import deliver_subscription

        sub = SimpleNamespace(id=1, name="hook", target_url="https://a.example/hook", secret=None, org_id=1)
        with patch("app.core.webhook_dispatcher.httpx.Client") as mock_client_cls:
            mock_client = mock_client_cls.return_value.__enter__.return_value
            mock_client.post.return_value = _FakeResponse(200)
            ok, status_code, error = deliver_subscription(sub, "metric.refreshed", {"event": "metric.refreshed"})

        self.assertTrue(ok)
        self.assertEqual(status_code, 200)
        self.assertIsNone(error)
        # body 应以 JSON 发送
        _, kwargs = mock_client.post.call_args
        self.assertEqual(kwargs["headers"]["Content-Type"], "application/json")

    def test_deliver_subscription_retries_then_fails(self):
        from app.core.webhook_dispatcher import deliver_subscription, MAX_ATTEMPTS

        sub = SimpleNamespace(id=1, name="hook", target_url="https://a.example/hook", secret=None, org_id=1)
        with patch("app.core.webhook_dispatcher.httpx.Client") as mock_client_cls:
            mock_client = mock_client_cls.return_value.__enter__.return_value
            mock_client.post.return_value = _FakeResponse(500)
            ok, status_code, error = deliver_subscription(sub, "metric.refreshed", {"event": "metric.refreshed"})

        self.assertFalse(ok)
        self.assertEqual(mock_client.post.call_count, MAX_ATTEMPTS)
        self.assertIn("500", error)

    def test_deliver_subscription_includes_signature_header_when_secret_set(self):
        from app.core.webhook_dispatcher import deliver_subscription, SIGNATURE_HEADER

        sub = SimpleNamespace(id=1, name="hook", target_url="https://a.example/hook", secret="topsecret", org_id=1)
        with patch("app.core.webhook_dispatcher.httpx.Client") as mock_client_cls:
            mock_client = mock_client_cls.return_value.__enter__.return_value
            mock_client.post.return_value = _FakeResponse(200)
            deliver_subscription(sub, "metric.refreshed", {"event": "metric.refreshed"})

        _, kwargs = mock_client.post.call_args
        self.assertIn(SIGNATURE_HEADER, kwargs["headers"])
        self.assertTrue(kwargs["headers"][SIGNATURE_HEADER].startswith("sha256="))


class WebhookDispatchTests(unittest.TestCase):
    def test_dispatch_sync_returns_matched_count(self):
        from app.core.webhook_dispatcher import dispatch_event

        db = _db()
        _add_subscription(db, name="hook-1", target_url="https://a.example/hook", events=["metric.refreshed"], org_id=1)
        _add_subscription(db, name="hook-2", target_url="https://b.example/hook", events=["metric.refreshed"], org_id=1)

        with patch("app.core.webhook_dispatcher.deliver_subscription", return_value=(True, 200, None)):
            count = dispatch_event(db, org_id=1, event_type="metric.refreshed", data={"metric_id": 1}, run_async=False)

        self.assertEqual(count, 2)

    def test_dispatch_no_matching_returns_zero_without_calling_delivery(self):
        from app.core.webhook_dispatcher import dispatch_event

        db = _db()
        _add_subscription(db, name="hook-other-org", target_url="https://a.example/hook", events=["metric.refreshed"], org_id=2)

        with patch("app.core.webhook_dispatcher.deliver_subscription") as mock_deliver:
            count = dispatch_event(db, org_id=1, event_type="metric.refreshed", run_async=False)

        self.assertEqual(count, 0)
        mock_deliver.assert_not_called()


if __name__ == "__main__":
    unittest.main()
