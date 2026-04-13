from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.alert import Alert
from app.models.alert_history import AlertHistory
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


@router.get("", response_model=AlertListResponse)
def list_alerts(
    datasource_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Alert)
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
    q = db.query(AlertHistory).order_by(AlertHistory.triggered_at.desc())
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
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="预警不存在")
    from app.core.alert_evaluator import evaluate_alert
    import threading
    t = threading.Thread(target=evaluate_alert, args=(alert_id,), daemon=True)
    t.start()
    return {"status": "ok", "message": "预警评估已触发，请稍后查看历史记录"}


@router.post("", response_model=AlertOut)
def create_alert(
    payload: AlertCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alert = Alert(**payload.model_dump(), created_by=current_user.id)
    db.add(alert)
    db.commit()
    db.refresh(alert)
    from app.core.alert_scheduler import upsert_alert_job
    upsert_alert_job(alert.id)
    return alert


@router.get("/{alert_id}", response_model=AlertOut)
def get_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="预警不存在")
    return alert


@router.put("/{alert_id}", response_model=AlertOut)
def update_alert(
    alert_id: int,
    payload: AlertUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="预警不存在")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(alert, key, value)
    db.commit()
    db.refresh(alert)
    from app.core.alert_scheduler import upsert_alert_job
    upsert_alert_job(alert_id)
    return alert


@router.delete("/{alert_id}")
def delete_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="预警不存在")
    db.delete(alert)
    db.commit()
    from app.core.alert_scheduler import remove_alert_job
    remove_alert_job(alert_id)
    return {"status": "ok"}
