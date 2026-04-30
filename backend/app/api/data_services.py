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
        "api_contract": {
            "type": "metric_definition",
            "sql_fragment": metric.formula,
        },
    }


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
    return {
        "id": dashboard.id,
        "title": dashboard.title,
        "description": dashboard.description,
        "layout_json": dashboard.layout_json,
        "filters_json": dashboard.filters_json,
        "version": dashboard.version,
        "embed": {
            "mode": "readonly",
            "sdk_hint": "GET /api/data-services/dashboards/{dashboard_id}/embed",
        },
    }


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
