import threading

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.scheduled_report import ScheduledReport
from app.models.user import User
from app.schemas.scheduled_report import (
    ScheduledReportCreate,
    ScheduledReportListResponse,
    ScheduledReportOut,
    ScheduledReportUpdate,
)

router = APIRouter(prefix="/scheduled-reports", tags=["scheduled_reports"])


@router.get("", response_model=ScheduledReportListResponse)
def list_reports(
    datasource_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(ScheduledReport)
    if datasource_id:
        q = q.filter(ScheduledReport.datasource_id == datasource_id)
    items = q.order_by(ScheduledReport.updated_at.desc()).all()
    return {"items": items, "total": len(items)}


@router.post("", response_model=ScheduledReportOut)
def create_report(
    payload: ScheduledReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = ScheduledReport(**payload.model_dump(), created_by=current_user.id)
    db.add(report)
    db.commit()
    db.refresh(report)

    from app.core.alert_scheduler import upsert_report_job
    upsert_report_job(report.id)
    return report


@router.get("/{report_id}", response_model=ScheduledReportOut)
def get_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = db.query(ScheduledReport).filter(ScheduledReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="定时报告不存在")
    return report


@router.put("/{report_id}", response_model=ScheduledReportOut)
def update_report(
    report_id: int,
    payload: ScheduledReportUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = db.query(ScheduledReport).filter(ScheduledReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="定时报告不存在")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(report, key, value)
    db.commit()
    db.refresh(report)

    from app.core.alert_scheduler import upsert_report_job
    upsert_report_job(report_id)
    return report


@router.delete("/{report_id}")
def delete_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = db.query(ScheduledReport).filter(ScheduledReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="定时报告不存在")
    db.delete(report)
    db.commit()

    from app.core.alert_scheduler import remove_report_job
    remove_report_job(report_id)
    return {"status": "ok"}


@router.post("/{report_id}/run")
def run_report_now(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually trigger a report immediately."""
    report = db.query(ScheduledReport).filter(ScheduledReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="定时报告不存在")

    from app.core.alert_scheduler import run_scheduled_report
    t = threading.Thread(target=run_scheduled_report, args=(report_id,), daemon=True)
    t.start()
    return {"status": "ok", "message": "报告已开始生成，稍后将发送到配置的通知渠道"}
