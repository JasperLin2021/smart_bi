from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from app.api.auth import get_current_user
from app.core.audit import try_record_audit_log
from app.db.session import get_db
from app.models.alert import Alert
from app.models.alert_history import AlertHistory
from app.models.datasource import DataSource
from app.models.user import User
from app.schemas.alert import AlertCreate, AlertUpdate, AlertOut, AlertListResponse

router = APIRouter(prefix="/alerts", tags=["alerts"])


class AlertHistoryItem(BaseModel):
    id: int
    alert_id: int
    alert_name: Optional[str] = None
    triggered_at: Optional[datetime] = None
    metric_value: Optional[str] = None
    condition_desc: Optional[str] = None
    notify_result: Optional[str] = None
    status: Optional[str] = None

    class Config:
        from_attributes = True


def _alert_scope(query, current_user: User):
    if current_user.role == "super_admin":
        return query
    return query.join(DataSource, Alert.datasource_id == DataSource.id).filter(
        DataSource.org_id == current_user.org_id
    )


def _history_scope(query, current_user: User):
    if current_user.role == "super_admin":
        return query
    return query.join(Alert, AlertHistory.alert_id == Alert.id).join(
        DataSource, Alert.datasource_id == DataSource.id
    ).filter(DataSource.org_id == current_user.org_id)


def _get_datasource_for_user(db: Session, datasource_id: int, current_user: User) -> DataSource:
    datasource = db.query(DataSource).filter(DataSource.id == datasource_id).first()
    if not datasource:
        raise HTTPException(status_code=404, detail="数据源不存在")
    if current_user.role != "super_admin" and datasource.org_id != current_user.org_id:
        raise HTTPException(status_code=403, detail="无权访问此数据源")
    return datasource


def _get_alert_for_user(db: Session, alert_id: int, current_user: User) -> Alert:
    alert = _alert_scope(db.query(Alert), current_user).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="预警不存在")
    return alert


@router.get("", response_model=AlertListResponse)
def list_alerts(
    datasource_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = _alert_scope(db.query(Alert), current_user)
    if datasource_id:
        q = q.filter(Alert.datasource_id == datasource_id)
    items = q.order_by(Alert.updated_at.desc()).all()
    return {"items": items, "total": len(items)}


@router.get("/history", response_model=List[AlertHistoryItem])
def list_alert_history(
    alert_id: Optional[int] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = _history_scope(db.query(AlertHistory), current_user).order_by(AlertHistory.triggered_at.desc())
    if alert_id:
        q = q.filter(AlertHistory.alert_id == alert_id)
    return q.limit(limit).all()


@router.post("/{alert_id}/run")
def run_alert_now(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually trigger an alert evaluation immediately."""
    alert = _get_alert_for_user(db, alert_id, current_user)
    from app.core.alert_evaluator import evaluate_alert
    import threading
    t = threading.Thread(target=evaluate_alert, args=(alert_id,), daemon=True)
    t.start()
    try_record_audit_log(
        db,
        actor=current_user,
        action="alert.run",
        resource_type="alert",
        resource_id=alert.id,
        resource_name=alert.name,
        message="预警手动评估已触发",
        detail={"datasource_id": alert.datasource_id},
    )
    return {"status": "ok", "message": "预警评估已触发，请稍后查看历史记录"}


@router.post("", response_model=AlertOut)
def create_alert(
    payload: AlertCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    datasource = _get_datasource_for_user(db, payload.datasource_id, current_user)
    alert = Alert(**payload.model_dump(), created_by=current_user.id)
    db.add(alert)
    db.commit()
    db.refresh(alert)
    from app.core.alert_scheduler import upsert_alert_job
    upsert_alert_job(alert.id)
    try_record_audit_log(
        db,
        actor=current_user,
        action="alert.create",
        resource_type="alert",
        resource_id=alert.id,
        resource_name=alert.name,
        org_id=datasource.org_id,
        message="预警已创建",
        detail={"datasource_id": alert.datasource_id},
    )
    return alert


@router.get("/{alert_id}", response_model=AlertOut)
def get_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alert = _get_alert_for_user(db, alert_id, current_user)
    return alert


@router.put("/{alert_id}", response_model=AlertOut)
def update_alert(
    alert_id: int,
    payload: AlertUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alert = _get_alert_for_user(db, alert_id, current_user)
    if payload.datasource_id is not None:
        _get_datasource_for_user(db, payload.datasource_id, current_user)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(alert, key, value)
    db.commit()
    db.refresh(alert)
    from app.core.alert_scheduler import upsert_alert_job
    upsert_alert_job(alert_id)
    datasource = db.query(DataSource).filter(DataSource.id == alert.datasource_id).first()
    try_record_audit_log(
        db,
        actor=current_user,
        action="alert.update",
        resource_type="alert",
        resource_id=alert.id,
        resource_name=alert.name,
        org_id=datasource.org_id if datasource else None,
        message="预警已更新",
        detail={"fields": list(payload.model_dump(exclude_unset=True).keys())},
    )
    return alert


@router.delete("/{alert_id}")
def delete_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alert = _get_alert_for_user(db, alert_id, current_user)
    datasource = db.query(DataSource).filter(DataSource.id == alert.datasource_id).first()
    alert_name = alert.name
    db.delete(alert)
    db.commit()
    from app.core.alert_scheduler import remove_alert_job
    remove_alert_job(alert_id)
    try_record_audit_log(
        db,
        actor=current_user,
        action="alert.delete",
        resource_type="alert",
        resource_id=alert_id,
        resource_name=alert_name,
        org_id=datasource.org_id if datasource else None,
        message="预警已删除",
    )
    return {"status": "ok"}
