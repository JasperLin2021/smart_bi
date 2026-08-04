"""Outbound webhook delivery for data service events.

Delivers subscribed events (metric.refreshed, dashboard.published,
action_item.closed) to external HTTP endpoints. Delivery is
fire-and-forget in a daemon thread so the main request flow is never
blocked; use ``run_async=False`` (or the test endpoint) for synchronous
delivery with an auditable result.
"""
import hashlib
import hmac
import json
import logging
import threading
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
from sqlalchemy.orm import Session

from app.core.audit import try_record_audit_log
from app.models.webhook_subscription import WebhookSubscription

logger = logging.getLogger(__name__)

SUPPORTED_EVENTS = ["metric.refreshed", "dashboard.published", "action_item.closed"]
SIGNATURE_HEADER = "X-SmartBI-Signature"
TIMEOUT_SECONDS = 10
MAX_ATTEMPTS = 2


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def build_event_payload(event_type: str, data: dict | None = None) -> dict:
    return {
        "event": event_type,
        "timestamp": _utcnow().isoformat(),
        "data": data or {},
    }


def sign_payload(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def matching_subscriptions(db: Session, org_id: int | None, event_type: str) -> list[WebhookSubscription]:
    subscriptions = (
        db.query(WebhookSubscription)
        .filter(WebhookSubscription.enabled == 1)
        .order_by(WebhookSubscription.id.asc())
        .all()
    )
    return [
        subscription
        for subscription in subscriptions
        if subscription.org_id == org_id and event_type in (subscription.events or [])
    ]


def deliver_subscription(
    subscription: WebhookSubscription,
    event_type: str,
    payload: dict,
) -> tuple[bool, int | None, str | None]:
    """POST the event payload to the subscription target, retrying once on failure."""
    body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if subscription.secret:
        headers[SIGNATURE_HEADER] = sign_payload(subscription.secret, body)

    last_error: str | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
                resp = client.post(subscription.target_url, content=body, headers=headers)
            if resp.status_code < 400:
                return True, resp.status_code, None
            last_error = f"HTTP {resp.status_code}"
        except Exception as exc:  # noqa: BLE001 - delivery must never break callers
            last_error = str(exc)
        logger.warning(
            "webhook delivery attempt %s failed: subscription=%s event=%s error=%s",
            attempt,
            subscription.id,
            event_type,
            last_error,
        )
    return False, None, last_error


def _deliver_all(
    event_type: str,
    payload: dict,
    subscriptions: list[WebhookSubscription],
    db: Session | None = None,
) -> list[tuple[int, bool]]:
    results: list[tuple[int, bool]] = []
    for subscription in subscriptions:
        success, status_code, error = deliver_subscription(subscription, event_type, payload)
        results.append((subscription.id, success))
        if success:
            logger.info("webhook delivered: subscription=%s event=%s", subscription.id, event_type)
        if db is not None:
            try_record_audit_log(
                db,
                actor=None,
                action="webhook.deliver",
                resource_type="webhook_subscription",
                resource_id=subscription.id,
                resource_name=subscription.name,
                org_id=subscription.org_id,
                status="success" if success else "failed",
                message="Webhook 已投递" if success else "Webhook 投递失败",
                detail={"event": event_type, "status_code": status_code, "error": error},
            )
    return results


def dispatch_event(
    db: Session,
    org_id: int | None,
    event_type: str,
    data: dict | None = None,
    *,
    run_async: bool = True,
) -> int:
    """Dispatch an event to matching enabled subscriptions of the org.

    Returns the number of matched subscriptions. With ``run_async=True``
    (default) delivery runs in a daemon thread (fire-and-forget, results
    logged); with ``run_async=False`` delivery is synchronous and each
    result is written to the audit log.
    """
    try:
        subscriptions = matching_subscriptions(db, org_id, event_type)
    except Exception:  # noqa: BLE001 - webhook lookup must never break the main flow
        db.rollback()
        logger.exception("webhook subscription lookup failed: event=%s", event_type)
        return 0
    if not subscriptions:
        return 0

    payload = build_event_payload(event_type, data)
    # Snapshot plain attribute values so async delivery never touches an
    # expired/closed request session.
    snapshots = [
        SimpleNamespace(
            id=subscription.id,
            name=subscription.name,
            target_url=subscription.target_url,
            secret=subscription.secret,
            org_id=subscription.org_id,
        )
        for subscription in subscriptions
    ]
    if run_async:
        thread = threading.Thread(
            target=_deliver_all,
            args=(event_type, payload, snapshots),
            kwargs={"db": None},
            daemon=True,
        )
        thread.start()
    else:
        _deliver_all(event_type, payload, snapshots, db=db)
    return len(snapshots)
