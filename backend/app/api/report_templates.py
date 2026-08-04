from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.audit import try_record_audit_log
from app.core.permissions import require_action
from app.core.report_exporter import SUPPORTED_EXPORT_TYPES, execute_report_export, get_export_dir
from app.core.report_writeback import execute_fill_writeback, has_writeback_target
from app.db.session import get_db
from app.models.dataset import Dataset
from app.models.report_template import ReportFillRecord, ReportRun, ReportTemplate, ReportTemplateVersion
from app.models.user import User
from app.schemas.report_template import (
    ReportExportRequest,
    ReportFillRequest,
    ReportPreviewRequest,
    ReportRunOut,
    ReportTemplateCreate,
    ReportTemplateListResponse,
    ReportTemplateOut,
    ReportTemplateUpdate,
    ReportTemplateVersionOut,
)

router = APIRouter(prefix="/report-templates", tags=["report-templates"])

VALID_REPORT_TYPES = {"paginated", "parameterized", "master_detail", "cross_tab", "fill_form", "word", "ai_html"}
VALID_STATUSES = {"draft", "published", "archived"}
VALID_VISIBILITIES = {"private", "org"}
VALID_EXPORT_TYPES = {"html", "excel", "pdf", "word"}


def _ensure_values(report_type: str | None = None, status: str | None = None, visibility: str | None = None) -> None:
    if report_type is not None and report_type not in VALID_REPORT_TYPES:
        raise HTTPException(status_code=400, detail="无效报表类型")
    if status is not None and status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="无效报表状态")
    if visibility is not None and visibility not in VALID_VISIBILITIES:
        raise HTTPException(status_code=400, detail="无效可见范围")


def _dataset_scope(query, user: User):
    if user.role == "super_admin":
        return query
    query = query.filter(Dataset.org_id == user.org_id)
    if user.role == "org_admin":
        return query
    return query.filter(or_(Dataset.status == "published", Dataset.owner_id == user.id))


def _get_dataset_for_user(db: Session, dataset_id: int, user: User) -> Dataset:
    dataset = _dataset_scope(db.query(Dataset), user).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")
    return dataset


def _template_scope(query, user: User):
    if user.role == "super_admin":
        return query
    query = query.filter(ReportTemplate.org_id == user.org_id)
    if user.role == "org_admin":
        return query
    return query.filter(or_(ReportTemplate.visibility == "org", ReportTemplate.owner_id == user.id))


def _get_template_for_user(db: Session, template_id: int, user: User) -> ReportTemplate:
    template = _template_scope(db.query(ReportTemplate), user).filter(ReportTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="报表模板不存在")
    return template


def _template_snapshot(template: ReportTemplate) -> dict[str, Any]:
    return {
        "name": template.name,
        "description": template.description,
        "dataset_id": template.dataset_id,
        "report_type": template.report_type,
        "layout_json": template.layout_json,
        "parameter_schema_json": template.parameter_schema_json,
        "binding_json": template.binding_json,
        "style_json": template.style_json,
        "permission_json": template.permission_json,
        "fill_schema_json": template.fill_schema_json,
        "distribution_json": template.distribution_json,
        "status": template.status,
        "visibility": template.visibility,
        "version": template.version,
    }


def _add_version(db: Session, template: ReportTemplate, user: User, changelog: str | None = None) -> ReportTemplateVersion:
    version = ReportTemplateVersion(
        template_id=template.id,
        version=template.version,
        snapshot_json=_template_snapshot(template),
        changelog=changelog,
        created_by=getattr(user, "id", None),
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version


@router.get("", response_model=ReportTemplateListResponse)
def list_report_templates(
    dataset_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_action(current_user, "report.read")
    query = _template_scope(db.query(ReportTemplate), current_user)
    if dataset_id:
        query = query.filter(ReportTemplate.dataset_id == dataset_id)
    items = query.order_by(ReportTemplate.updated_at.desc()).all()
    return {"items": items, "total": len(items)}


@router.post("", response_model=ReportTemplateOut)
def create_report_template(
    payload: ReportTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_action(current_user, "report.create")
    _ensure_values(payload.report_type, payload.status, payload.visibility)
    dataset = _get_dataset_for_user(db, payload.dataset_id, current_user)
    template = ReportTemplate(
        **payload.model_dump(),
        version=1,
        org_id=dataset.org_id,
        owner_id=getattr(current_user, "id", None),
        created_by=getattr(current_user, "id", None),
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    _add_version(db, template, current_user, "初始版本")
    try_record_audit_log(
        db,
        actor=current_user,
        action="report_template.create",
        resource_type="report_template",
        resource_id=template.id,
        resource_name=template.name,
        org_id=template.org_id,
        message="复杂报表模板已创建",
        detail={"dataset_id": template.dataset_id, "report_type": template.report_type},
    )
    return template


@router.get("/{template_id}", response_model=ReportTemplateOut)
def get_report_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_action(current_user, "report.read")
    return _get_template_for_user(db, template_id, current_user)


@router.put("/{template_id}", response_model=ReportTemplateOut)
def update_report_template(
    template_id: int,
    payload: ReportTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_action(current_user, "report.update")
    template = _get_template_for_user(db, template_id, current_user)
    updates = payload.model_dump(exclude_unset=True)
    changelog = updates.pop("changelog", None)
    _ensure_values(updates.get("report_type"), updates.get("status"), updates.get("visibility"))
    if "dataset_id" in updates:
        dataset = _get_dataset_for_user(db, updates["dataset_id"], current_user)
        template.org_id = dataset.org_id
    for key, value in updates.items():
        setattr(template, key, value)
    template.version = (template.version or 1) + 1
    db.commit()
    db.refresh(template)
    _add_version(db, template, current_user, changelog or "模板更新")
    try_record_audit_log(
        db,
        actor=current_user,
        action="report_template.update",
        resource_type="report_template",
        resource_id=template.id,
        resource_name=template.name,
        org_id=template.org_id,
        message="复杂报表模板已更新",
        detail={"fields": list(updates.keys()), "version": template.version},
    )
    return template


@router.delete("/{template_id}")
def delete_report_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_action(current_user, "report.delete")
    template = _get_template_for_user(db, template_id, current_user)
    name = template.name
    org_id = template.org_id
    db.query(ReportFillRecord).filter(ReportFillRecord.template_id == template_id).delete()
    db.query(ReportRun).filter(ReportRun.template_id == template_id).delete()
    db.query(ReportTemplateVersion).filter(ReportTemplateVersion.template_id == template_id).delete()
    db.delete(template)
    db.commit()
    try_record_audit_log(
        db,
        actor=current_user,
        action="report_template.delete",
        resource_type="report_template",
        resource_id=template_id,
        resource_name=name,
        org_id=org_id,
        message="复杂报表模板已删除",
    )
    return {"status": "ok"}


@router.get("/{template_id}/versions", response_model=list[ReportTemplateVersionOut])
def list_report_versions(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_action(current_user, "report.read")
    _get_template_for_user(db, template_id, current_user)
    return (
        db.query(ReportTemplateVersion)
        .filter(ReportTemplateVersion.template_id == template_id)
        .order_by(ReportTemplateVersion.version.desc())
        .all()
    )


@router.post("/{template_id}/preview")
def preview_report_template(
    template_id: int,
    payload: ReportPreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_action(current_user, "report.read")
    template = _get_template_for_user(db, template_id, current_user)
    dataset = _get_dataset_for_user(db, template.dataset_id, current_user)
    return {
        "template_id": template.id,
        "template_name": template.name,
        "version": template.version,
        "dataset": {"id": dataset.id, "name": dataset.name},
        "parameters": payload.parameters,
        "layout": template.layout_json or {"paper": "A4", "cells": []},
    }


@router.post("/{template_id}/export")
def export_report_template(
    template_id: int,
    payload: ReportExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_action(current_user, "report.export")
    if payload.export_type not in VALID_EXPORT_TYPES:
        raise HTTPException(status_code=400, detail="不支持的导出类型")
    if payload.export_type not in SUPPORTED_EXPORT_TYPES:
        raise HTTPException(status_code=400, detail=f"暂不支持 {payload.export_type} 导出，当前仅支持 excel")
    template = _get_template_for_user(db, template_id, current_user)
    run = ReportRun(
        template_id=template.id,
        version=template.version,
        run_type="export",
        export_type=payload.export_type,
        status="queued",
        parameters_json=payload.parameters,
        content_preview=f"{template.name} v{template.version} {payload.export_type} 导出任务已排队",
        org_id=template.org_id,
        created_by=getattr(current_user, "id", None),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    run.status = "running"
    db.commit()
    try:
        output_path, row_count = execute_report_export(db, template, run)
    except Exception as exc:
        run.status = "failed"
        run.error_message = str(exc)[:2000]
        run.finished_at = datetime.now()
        run.content_preview = f"{template.name} v{template.version} {payload.export_type} 导出失败"
    else:
        run.status = "completed"
        run.output_uri = output_path.name
        run.error_message = None
        run.finished_at = datetime.now()
        run.content_preview = f"{template.name} v{template.version} {payload.export_type} 导出完成，共 {row_count} 行数据"
    db.commit()
    db.refresh(run)
    try_record_audit_log(
        db,
        actor=current_user,
        action="report_template.export",
        resource_type="report_template",
        resource_id=template.id,
        resource_name=template.name,
        org_id=template.org_id,
        message="复杂报表导出已执行",
        detail={"export_type": payload.export_type, "run_id": run.id, "status": run.status},
    )
    return {"status": run.status, "run_id": run.id, "export_type": run.export_type}


@router.get("/runs/{run_id}/download")
def download_report_run(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_action(current_user, "report.export")
    run = db.query(ReportRun).filter(ReportRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="导出任务不存在")
    template = db.query(ReportTemplate).filter(ReportTemplate.id == run.template_id).first()
    if template is not None:
        # 复用模板的组织/可见范围校验；无权访问时抛出 404。
        _get_template_for_user(db, template.id, current_user)
    elif current_user.role != "super_admin" and run.org_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="导出任务不存在")
    if run.status != "completed" or not run.output_uri:
        raise HTTPException(status_code=400, detail="导出任务尚未完成，无法下载")
    export_dir = get_export_dir().resolve()
    # output_uri 只存文件名，这里再取 basename 防止路径穿越。
    path = (export_dir / Path(run.output_uri).name).resolve()
    if path.parent != export_dir or not path.exists():
        raise HTTPException(status_code=404, detail="导出文件不存在")
    return FileResponse(
        path,
        filename=path.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.post("/{template_id}/fill")
def submit_report_fill(
    template_id: int,
    payload: ReportFillRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_action(current_user, "report.fill")
    template = _get_template_for_user(db, template_id, current_user)
    schema = template.fill_schema_json if isinstance(template.fill_schema_json, dict) else {}
    required = {
        str(field.get("name"))
        for field in schema.get("fields", [])
        if isinstance(field, dict) and field.get("required") and field.get("name")
    }
    missing = sorted(name for name in required if payload.payload.get(name) in (None, ""))
    record = ReportFillRecord(
        template_id=template.id,
        payload_json=payload.payload,
        validation_status="error" if missing else "valid",
        validation_errors_json={"missing": missing} if missing else None,
        writeback_status="pending" if not missing else "blocked",
        org_id=template.org_id,
        submitted_by=getattr(current_user, "id", None),
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    message = None
    if not missing:
        if has_writeback_target(schema):
            try:
                execute_fill_writeback(db, schema, payload.payload)
            except Exception as exc:
                db.rollback()
                record.writeback_status = "failed"
                record.writeback_error = str(exc)[:2000]
                message = "填报数据已保存，但回写失败"
            else:
                record.writeback_status = "completed"
                record.writeback_error = None
                message = "填报数据已回写目标表"
            db.commit()
            db.refresh(record)
        else:
            message = "未配置回写目标，填报数据已保存并保持待回写状态"

    return {
        "status": record.validation_status,
        "record_id": record.id,
        "errors": record.validation_errors_json,
        "writeback_status": record.writeback_status,
        "message": message,
    }


@router.get("/{template_id}/runs", response_model=list[ReportRunOut])
def list_report_runs(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_action(current_user, "report.read")
    _get_template_for_user(db, template_id, current_user)
    return (
        db.query(ReportRun)
        .filter(ReportRun.template_id == template_id)
        .order_by(ReportRun.started_at.desc())
        .limit(100)
        .all()
    )
