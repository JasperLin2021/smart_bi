from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.audit import try_record_audit_log
from app.db.session import get_db
from app.models.dashboard_config import Dashboard
from app.models.datasource import DataSource
from app.models.metric import Metric
from app.models.user import User

router = APIRouter(prefix="/data-services", tags=["data_services"])


class WebhookPayload(BaseModel):
    event: str
    payload: dict | None = None


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
