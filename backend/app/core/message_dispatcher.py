from datetime import datetime, timezone
from typing import Callable

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.wechat_work import WECHAT_WORK_PROVIDER, WechatWorkClient
from app.models.integration import ExternalIdentity, IntegrationConfig, MessageDelivery

SUPPORTED_EVENT_TYPES = {
    "alert.triggered",
    "scheduled_report.generated",
    "action_item.assigned",
    "action_item.status_changed",
    "dashboard.comment.created",
    "dashboard.shared",
    "approval.requested",
}


class MessageEvent(BaseModel):
    event_type: str
    org_id: int | None = None
    recipient_user_ids: list[int] = []
    title: str
    content: str
    link_url: str | None = None


ClientFactory = Callable[[IntegrationConfig], WechatWorkClient]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _default_client_factory(config: IntegrationConfig) -> WechatWorkClient:
    return WechatWorkClient(
        corp_id=config.corp_id or "",
        agent_id=config.agent_id or "",
        app_secret=config.app_secret or "",
        callback_url=config.callback_url or "",
    )


def _get_enabled_config(db: Session) -> IntegrationConfig | None:
    return (
        db.query(IntegrationConfig)
        .filter(
            IntegrationConfig.provider == WECHAT_WORK_PROVIDER,
            IntegrationConfig.enabled == True,  # noqa: E712
        )
        .first()
    )


def _create_delivery(
    db: Session,
    event: MessageEvent,
    *,
    recipient_user_id: int,
    recipient_external_user_id: str | None = None,
) -> MessageDelivery:
    delivery = MessageDelivery(
        provider=WECHAT_WORK_PROVIDER,
        channel="wechat_app",
        event_type=event.event_type,
        recipient_user_id=recipient_user_id,
        recipient_external_user_id=recipient_external_user_id,
        org_id=event.org_id,
        title=event.title,
        content=event.content,
        link_url=event.link_url,
        status="pending",
    )
    db.add(delivery)
    db.flush()
    return delivery


def dispatch_message_event(
    db: Session,
    event: MessageEvent,
    *,
    client_factory: ClientFactory | None = None,
) -> list[MessageDelivery]:
    if event.event_type not in SUPPORTED_EVENT_TYPES:
        raise ValueError(f"不支持的消息事件类型: {event.event_type}")

    config = _get_enabled_config(db)
    client_factory = client_factory or _default_client_factory
    deliveries: list[MessageDelivery] = []
    token: str | None = None
    client = client_factory(config) if config else None

    for recipient_user_id in dict.fromkeys(event.recipient_user_ids):
        delivery = _create_delivery(db, event, recipient_user_id=recipient_user_id)
        deliveries.append(delivery)

        if not config or not config.corp_id or not config.agent_id or not config.app_secret:
            delivery.status = "failed"
            delivery.error_message = "企业微信应用消息未配置"
            continue

        identity = (
            db.query(ExternalIdentity)
            .filter(
                ExternalIdentity.provider == WECHAT_WORK_PROVIDER,
                ExternalIdentity.external_corp_id == config.corp_id,
                ExternalIdentity.user_id == recipient_user_id,
            )
            .first()
        )
        if not identity:
            delivery.status = "failed"
            delivery.error_message = "用户未绑定企业微信身份"
            continue

        delivery.recipient_external_user_id = identity.external_user_id
        try:
            if token is None:
                token = client.get_access_token()
            client.send_textcard(
                token,
                identity.external_user_id,
                event.title,
                event.content,
                event.link_url,
            )
            delivery.status = "success"
            delivery.sent_at = _utcnow()
        except Exception as exc:
            delivery.status = "failed"
            delivery.error_message = str(exc)

    db.commit()
    for delivery in deliveries:
        db.refresh(delivery)
    return deliveries
