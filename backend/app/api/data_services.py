from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.audit import try_record_audit_log
from app.core.webhook_dispatcher import (
    SUPPORTED_EVENTS,
    build_event_payload,
    deliver_subscription,
)
from app.db.session import get_db
from app.models.dashboard_config import Dashboard
from app.models.datasource import DataSource
from app.models.metric import Metric
from app.models.user import User
from app.models.webhook_subscription import WebhookSubscription

router = APIRouter(prefix="/data-services", tags=["data_services"])


class WebhookPayload(BaseModel):
    event: str
    payload: dict | None = None


class WebhookSubscriptionCreate(BaseModel):
    name: str
    target_url: str
    events: list[str]
    secret: str | None = None
    enabled: bool = True


class WebhookSubscriptionUpdate(BaseModel):
    name: str | None = None
    target_url: str | None = None
    events: list[str] | None = None
    secret: str | None = None
    enabled: bool | None = None


def _validate_events(events: list[str]) -> list[str]:
    invalid = [event for event in events if event not in SUPPORTED_EVENTS]
    if invalid:
        raise HTTPException(status_code=400, detail=f"不支持的事件类型: {', '.join(invalid)}")
    return events


def _subscription_for_user(db: Session, subscription_id: int, user: User) -> WebhookSubscription:
    subscription = db.query(WebhookSubscription).filter(WebhookSubscription.id == subscription_id).first()
    if not subscription:
        raise HTTPException(status_code=404, detail="Webhook 订阅不存在")
    if user.role != "super_admin" and subscription.org_id != user.org_id:
        raise HTTPException(status_code=403, detail="无权访问此订阅")
    return subscription


def _subscription_contract(subscription: WebhookSubscription) -> dict:
    return {
        "id": subscription.id,
        "org_id": subscription.org_id,
        "name": subscription.name,
        "target_url": subscription.target_url,
        "events": subscription.events or [],
        "secret_configured": bool(subscription.secret),
        "enabled": bool(subscription.enabled),
        "created_at": subscription.created_at.isoformat() if subscription.created_at else None,
        "updated_at": subscription.updated_at.isoformat() if subscription.updated_at else None,
    }


def _metric_for_user(db: Session, metric_id: int, user: User) -> tuple[Metric, DataSource | None]:
    metric = db.query(Metric).filter(Metric.id == metric_id).first()
    if not metric:
        raise HTTPException(status_code=404, detail="指标不存在")
    datasource = db.query(DataSource).filter(DataSource.id == metric.datasource_id).first()
    if user.role != "super_admin" and datasource and datasource.org_id != user.org_id:
        raise HTTPException(status_code=403, detail="无权访问此指标")
    return metric, datasource


def _metric_contract(metric: Metric, datasource: DataSource | None = None) -> dict:
    return {
        "id": metric.id,
        "name": metric.name,
        "definition": metric.definition,
        "formula": metric.formula,
        "unit": metric.unit,
        "aggregation": metric.aggregation,
        "datasource_id": metric.datasource_id,
        "datasource_name": datasource.name if datasource else None,
        "status": metric.status,
        "trust": {
            "certification_status": metric.certification_status,
            "certified_by": metric.certified_by,
            "certified_at": metric.certified_at,
            "caliber_version": metric.caliber_version,
            "quality_status": metric.quality_status,
            "quality_message": metric.quality_message,
            "data_updated_at": metric.data_updated_at,
        },
        "api_contract": {
            "type": "metric_definition",
            "endpoint": f"/api/data-services/metrics/{metric.id}",
            "sql_fragment": metric.formula,
            "response_fields": ["definition", "formula", "unit", "aggregation", "trust"],
        },
        "usage_examples": [
            f"GET /api/data-services/metrics/{metric.id}",
            "在业务系统中使用 formula 字段保持统一指标口径",
        ],
    }


def _dashboard_embed_contract(dashboard: Dashboard) -> dict:
    return {
        "id": dashboard.id,
        "title": dashboard.title,
        "description": dashboard.description,
        "layout_json": dashboard.layout_json,
        "filters_json": dashboard.filters_json,
        "version": dashboard.version,
        "embed": {
            "mode": "readonly",
            "endpoint": f"/api/data-services/dashboards/{dashboard.id}/embed",
            "script": f'<iframe src="/embed/dashboards/{dashboard.id}" title="{dashboard.title}"></iframe>',
            "sdk_hint": "GET /api/data-services/dashboards/{dashboard_id}/embed",
        },
    }


@router.get("/catalog")
def get_data_service_catalog(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    metric_query = db.query(Metric, DataSource).join(DataSource, Metric.datasource_id == DataSource.id)
    dashboard_query = db.query(Dashboard).filter(Dashboard.status == "published")
    if current_user.role != "super_admin":
        metric_query = metric_query.filter(DataSource.org_id == current_user.org_id)
        dashboard_query = dashboard_query.filter(Dashboard.org_id == current_user.org_id)

    metrics = [
        _metric_contract(metric, datasource)
        for metric, datasource in metric_query.filter(Metric.status == "published", Metric.is_active == 1)
        .order_by(Metric.updated_at.desc(), Metric.id.desc())
        .all()
    ]
    dashboards = [
        {
            "id": dashboard.id,
            "title": dashboard.title,
            "description": dashboard.description,
            "version": dashboard.version,
            "visibility": dashboard.visibility,
            "api_contract": {
                "type": "dashboard_embed",
                "endpoint": f"/api/data-services/dashboards/{dashboard.id}/embed",
                "response_fields": ["layout_json", "filters_json", "embed"],
            },
        }
        for dashboard in dashboard_query.order_by(Dashboard.updated_at.desc(), Dashboard.id.desc()).all()
    ]

    return {
        "metrics": metrics,
        "dashboards": dashboards,
        "webhooks": [
            {
                "name": "generic",
                "endpoint": "/api/data-services/webhooks/{name}",
                "subscriptions_endpoint": "/api/data-services/webhooks/subscriptions",
                "events": ["metric.refreshed", "dashboard.published", "action_item.closed"],
            }
        ],
        "sdk_examples": {
            "metric": "fetch('/api/data-services/metrics/{metric_id}')",
            "dashboard_embed": "fetch('/api/data-services/dashboards/{dashboard_id}/embed')",
            "webhook": "POST /api/data-services/webhooks/{name}",
        },
    }


@router.get("/metrics/{metric_id}")
def get_metric_service(
    metric_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    metric, datasource = _metric_for_user(db, metric_id, current_user)
    try_record_audit_log(
        db,
        actor=current_user,
        action="data_service.metric.read",
        resource_type="metric",
        resource_id=metric.id,
        resource_name=metric.name,
        org_id=datasource.org_id if datasource else current_user.org_id,
        message="指标服务 API 已读取",
    )
    return _metric_contract(metric, datasource)


@router.get("/dashboards/public/{share_token}/embed")
def get_public_dashboard_embed(
    share_token: str,
    db: Session = Depends(get_db),
):
    dashboard = (
        db.query(Dashboard)
        .filter(Dashboard.share_token == share_token, Dashboard.is_public == 1, Dashboard.status == "published")
        .first()
    )
    if not dashboard:
        raise HTTPException(status_code=404, detail="公开看板不存在")
    payload = _dashboard_embed_contract(dashboard)
    payload["embed"]["mode"] = "public_readonly"
    payload["embed"]["endpoint"] = f"/api/data-services/dashboards/public/{share_token}/embed"
    return payload


@router.get("/dashboards/{dashboard_id}/embed")
def get_dashboard_embed(
    dashboard_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dashboard = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
    if not dashboard:
        raise HTTPException(status_code=404, detail="看板不存在")
    if current_user.role != "super_admin" and dashboard.org_id != current_user.org_id:
        raise HTTPException(status_code=403, detail="无权访问此看板")
    if dashboard.status != "published" and dashboard.owner_id != current_user.id and current_user.role != "org_admin":
        raise HTTPException(status_code=403, detail="看板未发布")
    return _dashboard_embed_contract(dashboard)


@router.get("/webhooks/subscriptions")
def list_webhook_subscriptions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(WebhookSubscription)
    if current_user.role != "super_admin":
        query = query.filter(WebhookSubscription.org_id == current_user.org_id)
    subscriptions = query.order_by(WebhookSubscription.id.asc()).all()
    return [_subscription_contract(subscription) for subscription in subscriptions]


@router.post("/webhooks/subscriptions")
def create_webhook_subscription(
    payload: WebhookSubscriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subscription = WebhookSubscription(
        org_id=current_user.org_id,
        name=payload.name,
        target_url=payload.target_url,
        events=_validate_events(payload.events),
        secret=payload.secret,
        enabled=1 if payload.enabled else 0,
        created_by=current_user.id,
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    try_record_audit_log(
        db,
        actor=current_user,
        action="data_service.webhook_subscription.create",
        resource_type="webhook_subscription",
        resource_id=subscription.id,
        resource_name=subscription.name,
        org_id=current_user.org_id,
        message="Webhook 订阅已创建",
        detail={"events": subscription.events, "target_url": subscription.target_url},
    )
    return _subscription_contract(subscription)


@router.put("/webhooks/subscriptions/{subscription_id}")
def update_webhook_subscription(
    subscription_id: int,
    payload: WebhookSubscriptionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subscription = _subscription_for_user(db, subscription_id, current_user)
    values = payload.model_dump(exclude_unset=True)
    if "events" in values and values["events"] is not None:
        values["events"] = _validate_events(values["events"])
    if "enabled" in values and values["enabled"] is not None:
        values["enabled"] = 1 if values["enabled"] else 0
    for key, value in values.items():
        if value is not None:
            setattr(subscription, key, value)
    db.commit()
    db.refresh(subscription)
    try_record_audit_log(
        db,
        actor=current_user,
        action="data_service.webhook_subscription.update",
        resource_type="webhook_subscription",
        resource_id=subscription.id,
        resource_name=subscription.name,
        org_id=subscription.org_id,
        message="Webhook 订阅已更新",
        detail={"fields": list(values.keys())},
    )
    return _subscription_contract(subscription)


@router.delete("/webhooks/subscriptions/{subscription_id}")
def delete_webhook_subscription(
    subscription_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subscription = _subscription_for_user(db, subscription_id, current_user)
    resource_name = subscription.name
    org_id = subscription.org_id
    db.delete(subscription)
    db.commit()
    try_record_audit_log(
        db,
        actor=current_user,
        action="data_service.webhook_subscription.delete",
        resource_type="webhook_subscription",
        resource_id=subscription_id,
        resource_name=resource_name,
        org_id=org_id,
        message="Webhook 订阅已删除",
    )
    return {"status": "ok"}


@router.post("/webhooks/subscriptions/{subscription_id}/test")
def test_webhook_subscription(
    subscription_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subscription = _subscription_for_user(db, subscription_id, current_user)
    event_type = (subscription.events or [SUPPORTED_EVENTS[0]])[0]
    payload = build_event_payload(event_type, {"test": True, "subscription_id": subscription.id})
    success, status_code, error = deliver_subscription(subscription, event_type, payload)
    try_record_audit_log(
        db,
        actor=current_user,
        action="data_service.webhook_subscription.test",
        resource_type="webhook_subscription",
        resource_id=subscription.id,
        resource_name=subscription.name,
        org_id=subscription.org_id,
        status="success" if success else "failed",
        message="Webhook 测试投递成功" if success else "Webhook 测试投递失败",
        detail={"event": event_type, "status_code": status_code, "error": error},
    )
    return {"status": "delivered" if success else "failed", "status_code": status_code, "error": error}


@router.post("/webhooks/{name}")
def receive_webhook(
    name: str,
    payload: WebhookPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try_record_audit_log(
        db,
        actor=current_user,
        action="data_service.webhook",
        resource_type="webhook",
        resource_name=name,
        org_id=current_user.org_id,
        message="Webhook 已接收",
        detail={"event": payload.event, "payload": payload.payload},
    )
    return {"status": "accepted", "name": name, "event": payload.event}
