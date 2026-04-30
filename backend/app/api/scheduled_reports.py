import threading

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.audit import try_record_audit_log
from app.db.session import get_db
from app.models.datasource import DataSource
from app.models.scheduled_report import ScheduledReport
from app.models.user import User
from app.schemas.scheduled_report import (
    ScheduledReportCreate,
    ScheduledReportListResponse,
    ScheduledReportOut,
    ScheduledReportUpdate,
)

router = APIRouter(prefix="/scheduled-reports", tags=["scheduled_reports"])


def _report_scope(query, current_user: User):
    if current_user.role == "super_admin":
        return query
    return query.join(DataSource, ScheduledReport.datasource_id == DataSource.id).filter(
        DataSource.org_id == current_user.org_id
    )


def _get_datasource_for_user(db: Session, datasource_id: int, current_user: User) -> DataSource:
    datasource = db.query(DataSource).filter(DataSource.id == datasource_id).first()
    if not datasource:
        raise HTTPException(status_code=404, detail="数据源不存在")
    if current_user.role != "super_admin" and datasource.org_id != current_user.org_id:
        raise HTTPException(status_code=403, detail="无权访问此数据源")
    return datasource


def _get_report_for_user(db: Session, report_id: int, current_user: User) -> ScheduledReport:
    report = _report_scope(db.query(ScheduledReport), current_user).filter(
        ScheduledReport.id == report_id
    ).first()
    if not report:
        raise HTTPException(status_code=404, detail="定时报告不存在")
    return report


@router.get("", response_model=ScheduledReportListResponse)
def list_reports(
    datasource_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = _report_scope(db.query(ScheduledReport), current_user)
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
    datasource = _get_datasource_for_user(db, payload.datasource_id, current_user)
    report = ScheduledReport(**payload.model_dump(), created_by=current_user.id)
    db.add(report)
    db.commit()
    db.refresh(report)

    from app.core.alert_scheduler import upsert_report_job
    upsert_report_job(report.id)
    try_record_audit_log(
        db,
        actor=current_user,
        action="scheduled_report.create",
        resource_type="scheduled_report",
        resource_id=report.id,
        resource_name=report.name,
        org_id=datasource.org_id,
        message="定时报告已创建",
        detail={"datasource_id": report.datasource_id, "cron_expression": report.cron_expression},
    )
    return report


@router.get("/{report_id}", response_model=ScheduledReportOut)
def get_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = _get_report_for_user(db, report_id, current_user)
    return report


@router.put("/{report_id}", response_model=ScheduledReportOut)
def update_report(
    report_id: int,
    payload: ScheduledReportUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = _get_report_for_user(db, report_id, current_user)
    if payload.datasource_id is not None:
        _get_datasource_for_user(db, payload.datasource_id, current_user)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(report, key, value)
    db.commit()
    db.refresh(report)

    from app.core.alert_scheduler import upsert_report_job
    upsert_report_job(report_id)
    datasource = db.query(DataSource).filter(DataSource.id == report.datasource_id).first()
    try_record_audit_log(
        db,
        actor=current_user,
        action="scheduled_report.update",
        resource_type="scheduled_report",
        resource_id=report.id,
        resource_name=report.name,
        org_id=datasource.org_id if datasource else None,
        message="定时报告已更新",
        detail={"fields": list(payload.model_dump(exclude_unset=True).keys())},
    )
    return report


@router.delete("/{report_id}")
def delete_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = _get_report_for_user(db, report_id, current_user)
    datasource = db.query(DataSource).filter(DataSource.id == report.datasource_id).first()
    report_name = report.name
    db.delete(report)
    db.commit()

    from app.core.alert_scheduler import remove_report_job
    remove_report_job(report_id)
    try_record_audit_log(
        db,
        actor=current_user,
        action="scheduled_report.delete",
        resource_type="scheduled_report",
        resource_id=report_id,
        resource_name=report_name,
        org_id=datasource.org_id if datasource else None,
        message="定时报告已删除",
    )
    return {"status": "ok"}


@router.post("/{report_id}/run")
def run_report_now(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually trigger a report immediately."""
    report = _get_report_for_user(db, report_id, current_user)

    from app.core.alert_scheduler import run_scheduled_report
    t = threading.Thread(target=run_scheduled_report, args=(report_id,), daemon=True)
    t.start()
    try_record_audit_log(
        db,
        actor=current_user,
        action="scheduled_report.run",
        resource_type="scheduled_report",
        resource_id=report.id,
        resource_name=report.name,
        message="定时报告已手动触发",
        detail={"datasource_id": report.datasource_id},
    )
    return {"status": "ok", "message": "报告已开始生成，稍后将发送到配置的通知渠道"}
