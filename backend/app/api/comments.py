import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.api.auth import get_current_user
from app.core.message_dispatcher import MessageEvent, dispatch_message_event
from app.db.session import get_db
from app.models.dashboard_comment import DashboardComment
from app.models.dashboard_config import Dashboard
from app.models.user import User

router = APIRouter(prefix="/dashboards", tags=["comments"])
logger = logging.getLogger(__name__)


class CommentCreate(BaseModel):
    content: str


class CommentOut(BaseModel):
    id: int
    dashboard_id: int
    user_id: int
    username: str
    content: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


def _check_dashboard_access(db: Session, dashboard_id: int, user: User) -> Dashboard:
    dash = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
    if not dash:
        raise HTTPException(status_code=404, detail="看板不存在")
    if user.role == "super_admin":
        return dash
    if dash.org_id and dash.org_id != user.org_id:
        raise HTTPException(status_code=403, detail="无权访问此看板")
    return dash


def _comment_recipients(dashboard: Dashboard, author_id: int) -> list[int]:
    values = [dashboard.owner_id]
    if isinstance(dashboard.shared_user_ids, list):
        values.extend(dashboard.shared_user_ids)
    result: list[int] = []
    for value in values:
        if value is None or value == author_id or value in result:
            continue
        result.append(int(value))
    return result


def _safe_dispatch_comment_event(db: Session, event: MessageEvent) -> None:
    if not event.recipient_user_ids:
        return
    try:
        dispatch_message_event(db, event)
    except Exception as exc:
        logger.error("Dashboard comment message dispatch failed: %s", exc)


@router.get("/{dashboard_id}/comments", response_model=List[CommentOut])
def list_comments(
    dashboard_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_dashboard_access(db, dashboard_id, current_user)
    return (
        db.query(DashboardComment)
        .filter(DashboardComment.dashboard_id == dashboard_id)
        .order_by(DashboardComment.created_at.asc())
        .all()
    )


@router.post("/{dashboard_id}/comments", response_model=CommentOut)
def create_comment(
    dashboard_id: int,
    payload: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="评论内容不能为空")
    if len(content) > 2000:
        raise HTTPException(status_code=400, detail="评论内容不能超过 2000 字")

    dashboard = _check_dashboard_access(db, dashboard_id, current_user)

    comment = DashboardComment(
        dashboard_id=dashboard_id,
        user_id=current_user.id,
        username=current_user.username,
        content=content,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    _safe_dispatch_comment_event(
        db,
        MessageEvent(
            event_type="dashboard.comment.created",
            org_id=dashboard.org_id,
            recipient_user_ids=_comment_recipients(dashboard, current_user.id),
            title=f"看板评论：{dashboard.title}",
            content=f"{current_user.username} 评论：{content}",
            link_url=f"/dashboard-center?dashboard_id={dashboard.id}",
        ),
    )
    return comment


@router.delete("/{dashboard_id}/comments/{comment_id}")
def delete_comment(
    dashboard_id: int,
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_dashboard_access(db, dashboard_id, current_user)
    comment = db.query(DashboardComment).filter(
        DashboardComment.id == comment_id,
        DashboardComment.dashboard_id == dashboard_id,
    ).first()
    if not comment:
        raise HTTPException(status_code=404, detail="评论不存在")
    if comment.user_id != current_user.id and current_user.role not in ("super_admin", "org_admin"):
        raise HTTPException(status_code=403, detail="只能删除自己的评论")
    db.delete(comment)
    db.commit()
    return {"status": "ok"}
