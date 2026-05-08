import threading

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.audit import try_record_audit_log
from app.db.session import get_db
from app.models.dataset import Dataset
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
    return (
        query
        .join(Dataset, ScheduledReport.dataset_id == Dataset.id)
        .filter(Dataset.org_id == current_user.org_id)
    )


def _get_dataset_for_user(db: Session, dataset_id: int, current_user: User) -> Dataset:
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")
    if current_user.role != "super_admin" and dataset.org_id != current_user.org_id:
        raise HTTPException(status_code=403, detail="无权访问此数据集")
    return dataset


def _get_report_for_user(db: Session, report_id: int, current_user: User) -> ScheduledReport:
    report = _report_scope(db.query(ScheduledReport), current_user).filter(
        ScheduledReport.id == report_id
    ).first()
    if not report:
        raise HTTPException(status_code=404, detail="定时报告不存在")
    return report


@router.get("", response_model=ScheduledReportListResponse)
def list_reports(
    dataset_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = _report_scope(db.query(ScheduledReport), current_user)
    if dataset_id:
        q = q.filter(ScheduledReport.dataset_id == dataset_id)
    items = q.order_by(ScheduledReport.updated_at.desc()).all()
    return {"items": items, "total": len(items)}


@router.post("", response_model=ScheduledReportOut)
def create_report(
    payload: ScheduledReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = _get_dataset_for_user(db, payload.dataset_id, current_user)
    data = payload.model_dump()
    data["datasource_id"] = dataset.datasource_id
    report = ScheduledReport(**data, created_by=current_user.id)
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
        org_id=dataset.org_id,
        message="定时报告已创建",
        detail={"dataset_id": report.dataset_id, "cron_expression": report.cron_expression},
    )
    return report


@router.get("/{report_id}", response_model=ScheduledReportOut)
def get_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _get_report_for_user(db, report_id, current_user)


@router.put("/{report_id}", response_model=ScheduledReportOut)
def update_report(
    report_id: int,
    payload: ScheduledReportUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = _get_report_for_user(db, report_id, current_user)
    updates = payload.model_dump(exclude_unset=True)
    if "dataset_id" in updates:
        dataset = _get_dataset_for_user(db, updates["dataset_id"], current_user)
        updates["datasource_id"] = dataset.datasource_id
    for key, value in updates.items():
        setattr(report, key, value)
    db.commit()
    db.refresh(report)

    from app.core.alert_scheduler import upsert_report_job
    upsert_report_job(report_id)
    dataset = db.query(Dataset).filter(Dataset.id == report.dataset_id).first()
    try_record_audit_log(
        db,
        actor=current_user,
        action="scheduled_report.update",
        resource_type="scheduled_report",
        resource_id=report.id,
        resource_name=report.name,
        org_id=dataset.org_id if dataset else None,
        message="定时报告已更新",
        detail={"fields": list(updates.keys())},
    )
    return report


@router.delete("/{report_id}")
def delete_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = _get_report_for_user(db, report_id, current_user)
    dataset = db.query(Dataset).filter(Dataset.id == report.dataset_id).first()
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
        org_id=dataset.org_id if dataset else None,
        message="定时报告已删除",
    )
    return {"status": "ok"}


@router.post("/{report_id}/run")
def run_report_now(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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
        detail={"dataset_id": report.dataset_id},
    )
    return {"status": "ok", "message": "报告已开始生成，稍后将发送到配置的通知渠道"}


@router.get("/{report_id}/logs")
def get_report_logs(
    report_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_report_for_user(db, report_id, current_user)
    from app.models.report_execution_log import ReportExecutionLog
    logs = (
        db.query(ReportExecutionLog)
        .filter(ReportExecutionLog.report_id == report_id)
        .order_by(ReportExecutionLog.run_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": log.id,
            "report_id": log.report_id,
            "report_name": log.report_name,
            "status": log.status,
            "content_preview": log.content_preview,
            "notify_result": log.notify_result,
            "error_message": log.error_message,
            "run_at": log.run_at,
        }
        for log in logs
    ]
