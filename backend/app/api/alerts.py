from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from app.api.auth import get_current_user
from app.core.audit import try_record_audit_log
from app.core.safe_delete import assert_alert_can_delete
from app.db.session import get_db
from app.models.alert import Alert
from app.models.alert_history import AlertHistory
from app.models.dataset import Dataset
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
    return (
        query
        .join(Dataset, Alert.dataset_id == Dataset.id)
        .filter(Dataset.org_id == current_user.org_id)
    )


def _history_scope(query, current_user: User):
    if current_user.role == "super_admin":
        return query
    return (
        query
        .join(Alert, AlertHistory.alert_id == Alert.id)
        .join(Dataset, Alert.dataset_id == Dataset.id)
        .filter(Dataset.org_id == current_user.org_id)
    )


def _get_dataset_for_user(db: Session, dataset_id: int, current_user: User) -> Dataset:
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")
    if current_user.role != "super_admin" and dataset.org_id != current_user.org_id:
        raise HTTPException(status_code=403, detail="无权访问此数据集")
    return dataset


def _get_alert_for_user(db: Session, alert_id: int, current_user: User) -> Alert:
    alert = _alert_scope(db.query(Alert), current_user).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="预警不存在")
    return alert


@router.get("", response_model=AlertListResponse)
def list_alerts(
    dataset_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = _alert_scope(db.query(Alert), current_user)
    if dataset_id:
        q = q.filter(Alert.dataset_id == dataset_id)
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
        detail={"dataset_id": alert.dataset_id},
    )
    return {"status": "ok", "message": "预警评估已触发，请稍后查看历史记录"}


@router.post("", response_model=AlertOut)
def create_alert(
    payload: AlertCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = _get_dataset_for_user(db, payload.dataset_id, current_user)
    data = payload.model_dump()
    data["datasource_id"] = dataset.datasource_id
    alert = Alert(**data, created_by=current_user.id)
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
        org_id=dataset.org_id,
        message="预警已创建",
        detail={"dataset_id": alert.dataset_id},
    )
    return alert


@router.get("/{alert_id}", response_model=AlertOut)
def get_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _get_alert_for_user(db, alert_id, current_user)


@router.put("/{alert_id}", response_model=AlertOut)
def update_alert(
    alert_id: int,
    payload: AlertUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alert = _get_alert_for_user(db, alert_id, current_user)
    updates = payload.model_dump(exclude_unset=True)
    if "dataset_id" in updates:
        dataset = _get_dataset_for_user(db, updates["dataset_id"], current_user)
        updates["datasource_id"] = dataset.datasource_id
    for key, value in updates.items():
        setattr(alert, key, value)
    db.commit()
    db.refresh(alert)
    from app.core.alert_scheduler import upsert_alert_job
    upsert_alert_job(alert_id)
    dataset = db.query(Dataset).filter(Dataset.id == alert.dataset_id).first()
    try_record_audit_log(
        db,
        actor=current_user,
        action="alert.update",
        resource_type="alert",
        resource_id=alert.id,
        resource_name=alert.name,
        org_id=dataset.org_id if dataset else None,
        message="预警已更新",
        detail={"fields": list(updates.keys())},
    )
    return alert


@router.delete("/{alert_id}")
def delete_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alert = _get_alert_for_user(db, alert_id, current_user)
    assert_alert_can_delete(db, alert)
    dataset = db.query(Dataset).filter(Dataset.id == alert.dataset_id).first()
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
        org_id=dataset.org_id if dataset else None,
        message="预警已删除",
    )
    return {"status": "ok"}


class CreateActionItemFromAlertRequest(BaseModel):
    title: Optional[str] = None
    assignee_id: Optional[int] = None
    priority: Optional[str] = "high"
    due_date: Optional[str] = None


@router.post("/{alert_id}/create-action-item")
def create_action_item_from_alert(
    alert_id: int,
    payload: CreateActionItemFromAlertRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.action_item import ActionItem
    from app.models.alert_history import AlertHistory
    import datetime as dt

    alert = _get_alert_for_user(db, alert_id, current_user)
    latest_history = (
        db.query(AlertHistory)
        .filter(AlertHistory.alert_id == alert_id)
        .order_by(AlertHistory.id.desc())
        .first()
    )
    condition_desc = latest_history.condition_desc if latest_history else ""
    metric_value = latest_history.metric_value if latest_history else ""

    title = payload.title or f"[预警] {alert.name} 已触发"
    description = f"触发条件：{condition_desc}\n当前值：{metric_value}"

    due = None
    if payload.due_date:
        try:
            due = dt.date.fromisoformat(payload.due_date)
        except ValueError:
            pass

    dataset = db.query(Dataset).filter(Dataset.id == alert.dataset_id).first()
    item = ActionItem(
        title=title,
        description=description,
        source_type="alert",
        source_id=str(alert_id),
        source_payload={"alert_name": alert.name, "condition": condition_desc, "value": metric_value},
        linked_metric_id=alert.metric_id,
        owner_id=payload.assignee_id,
        priority=payload.priority or "high",
        due_date=due,
        status="open",
        org_id=dataset.org_id if dataset else current_user.org_id,
        created_by=current_user.id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"status": "ok", "action_item_id": item.id}
