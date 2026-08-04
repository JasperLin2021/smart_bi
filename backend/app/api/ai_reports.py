from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.ai_report import AiReport
from app.models.report_template import ReportTemplate
from app.models.user import User
from app.schemas.ai_report import (
    AiReportCreate,
    AiReportListResponse,
    AiReportOut,
    AiReportSharedOut,
)

router = APIRouter(prefix="/ai-reports", tags=["ai-reports"])


def _report_scope(query, user: User):
    if user.role == "super_admin":
        return query
    return query.filter(AiReport.org_id == user.org_id)


def _get_report_for_user(db: Session, report_id: int, user: User) -> AiReport:
    report = _report_scope(db.query(AiReport), user).filter(AiReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="AI 报表不存在")
    return report


def _can_manage_report(user: User, report: AiReport) -> bool:
    if user.role == "super_admin":
        return True
    if user.role == "org_admin" and report.org_id == user.org_id:
        return True
    return report.owner_id == user.id


def _get_manageable_report(db: Session, report_id: int, user: User) -> AiReport:
    report = _get_report_for_user(db, report_id, user)
    if not _can_manage_report(user, report):
        raise HTTPException(status_code=403, detail="无权操作此 AI 报表")
    return report


@router.post("", response_model=AiReportOut)
def create_ai_report(
    payload: AiReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="标题不能为空")
    if not payload.html.strip():
        raise HTTPException(status_code=400, detail="报表内容不能为空")
    report = AiReport(
        title=title,
        html=payload.html,
        conversation_json=payload.conversation_json,
        org_id=current_user.org_id,
        owner_id=getattr(current_user, "id", None),
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.get("", response_model=AiReportListResponse)
def list_ai_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = _report_scope(db.query(AiReport), current_user).order_by(AiReport.updated_at.desc()).all()
    return {"items": items, "total": len(items)}


@router.get("/shared/{token}", response_model=AiReportSharedOut)
def get_shared_ai_report(token: str, db: Session = Depends(get_db)):
    """公开分享访问：无需登录，凭 share_token 返回标题与 HTML。"""
    report = db.query(AiReport).filter(AiReport.share_token == token).first()
    if not report:
        raise HTTPException(status_code=404, detail="分享的 AI 报表不存在")
    return report


@router.get("/{report_id}", response_model=AiReportOut)
def get_ai_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _get_report_for_user(db, report_id, current_user)


@router.delete("/{report_id}")
def delete_ai_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = _get_manageable_report(db, report_id, current_user)
    db.delete(report)
    db.commit()
    return {"status": "ok"}


@router.post("/{report_id}/share")
def share_ai_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = _get_manageable_report(db, report_id, current_user)
    if not report.share_token:
        report.share_token = secrets.token_urlsafe(24)
        db.commit()
        db.refresh(report)
    return {"share_token": report.share_token}


@router.post("/{report_id}/unshare")
def unshare_ai_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = _get_manageable_report(db, report_id, current_user)
    report.share_token = None
    db.commit()
    return {"status": "ok"}


@router.post("/{report_id}/publish-to-report-center")
def publish_ai_report_to_report_center(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """把 AI 报表发布为报表中心的 ai_html 类型模板（无关联数据集）。"""
    report = _get_report_for_user(db, report_id, current_user)
    template = ReportTemplate(
        name=report.title,
        report_type="ai_html",
        layout_json={"kind": "html", "html": report.html},
        dataset_id=None,
        status="published",
        visibility="private",
        version=1,
        org_id=report.org_id,
        owner_id=getattr(current_user, "id", None),
        created_by=getattr(current_user, "id", None),
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return {"template_id": template.id}
