import secrets
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.api.embed import EmbedPublicData, resolve_dashboard_public_data
from app.core.audit import try_record_audit_log
from app.core.message_dispatcher import MessageEvent, dispatch_message_event
from app.core.webhook_dispatcher import dispatch_event
from app.core.safe_delete import assert_dashboard_can_delete, delete_catalog_asset
from app.db.session import get_db
from app.models.catalog import DataAsset
from app.models.dashboard_config import Dashboard
from app.models.user import User
from app.schemas.dashboard_center import (
    DashboardCreate,
    DashboardListResponse,
    DashboardOut,
    DashboardShareUpdate,
    DashboardUpdate,
)

router = APIRouter(prefix="/dashboards", tags=["dashboards"])
logger = logging.getLogger(__name__)

VALID_DASHBOARD_STATUSES = {"draft", "published", "archived"}
VALID_VISIBILITIES = {"private", "org"}


def _ensure_dashboard_values(status: str | None = None, visibility: str | None = None) -> None:
    if status is not None and status not in VALID_DASHBOARD_STATUSES:
        raise HTTPException(status_code=400, detail="无效看板状态")
    if visibility is not None and visibility not in VALID_VISIBILITIES:
        raise HTTPException(status_code=400, detail="无效看板可见范围")


def _can_manage_dashboard(user: User, dashboard: Dashboard) -> bool:
    if user.role == "super_admin":
        return True
    if user.role == "org_admin" and dashboard.org_id == user.org_id:
        return True
    return dashboard.owner_id == user.id


def _apply_visibility(query, user: User):
    if user.role == "super_admin":
        return query

    query = query.filter(Dashboard.org_id == user.org_id)
    if user.role == "org_admin":
        return query

    return query.filter(or_(Dashboard.status == "published", Dashboard.owner_id == user.id))


def _sync_dashboard_asset(db: Session, dashboard: Dashboard) -> None:
    asset = (
        db.query(DataAsset)
        .filter(DataAsset.asset_type == "dashboard", DataAsset.asset_id == dashboard.id)
        .first()
    )
    if not asset:
        asset = DataAsset(asset_type="dashboard", asset_id=dashboard.id)
        db.add(asset)
    asset.name = dashboard.title
    asset.description = dashboard.description
    asset.org_id = dashboard.org_id
    asset.owner_id = dashboard.owner_id
    asset.status = dashboard.status
    asset.metadata_json = {
        "visibility": dashboard.visibility,
        "is_public": bool(dashboard.is_public),
        "version": dashboard.version,
    }


def _shared_recipients(shared_user_ids, actor_id: int | None) -> list[int]:
    result: list[int] = []
    if not isinstance(shared_user_ids, list):
        return result
    for value in shared_user_ids:
        if value is None:
            continue
        user_id = int(value)
        if user_id == actor_id or user_id in result:
            continue
        result.append(user_id)
    return result


def _safe_dispatch_dashboard_event(db: Session, event: MessageEvent) -> None:
    if not event.recipient_user_ids:
        return
    try:
        dispatch_message_event(db, event)
    except Exception as exc:
        logger.error("Dashboard message dispatch failed: %s", exc)


@router.get("", response_model=DashboardListResponse)
def list_dashboards(
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = _apply_visibility(db.query(Dashboard), current_user)
    if status:
        query = query.filter(Dashboard.status == status)
    return {"items": query.order_by(Dashboard.id.desc()).all()}


@router.post("", response_model=DashboardOut)
def create_dashboard(
    payload: DashboardCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_dashboard_values(payload.status, payload.visibility)
    org_id = payload.org_id if current_user.role == "super_admin" else current_user.org_id
    dashboard = Dashboard(
        **payload.model_dump(exclude={"org_id", "owner_id"}),
        org_id=org_id,
        owner_id=payload.owner_id or current_user.id,
    )
    db.add(dashboard)
    db.flush()
    if dashboard.status == "published":
        _sync_dashboard_asset(db, dashboard)
    db.commit()
    db.refresh(dashboard)
    try_record_audit_log(
        db,
        actor=current_user,
        action="dashboard.create",
        resource_type="dashboard",
        resource_id=dashboard.id,
        resource_name=dashboard.title,
        org_id=dashboard.org_id,
        message="看板已创建",
        detail={"status": dashboard.status, "visibility": dashboard.visibility},
    )
    return dashboard


def _get_public_dashboard(db: Session, share_token: str) -> Dashboard:
    dashboard = (
        db.query(Dashboard)
        .filter(Dashboard.share_token == share_token, Dashboard.is_public == 1)
        .first()
    )
    if not dashboard:
        raise HTTPException(status_code=404, detail="公开看板不存在")
    return dashboard


@router.get("/public/{share_token}", response_model=DashboardOut)
def get_public_dashboard(
    share_token: str,
    db: Session = Depends(get_db),
):
    return _get_public_dashboard(db, share_token)


@router.get("/public/{share_token}/data", response_model=EmbedPublicData)
def get_public_dashboard_data(
    share_token: str,
    db: Session = Depends(get_db),
):
    """公开分享页取数：按 share_token 解析看板并执行各图表 SQL，返回与 embed 一致的数据结构。

    无需登录鉴权；仅 is_public=1 且 share_token 匹配的看板可访问。单图失败不阻断整板。
    """
    dashboard = _get_public_dashboard(db, share_token)
    return resolve_dashboard_public_data(db, dashboard)


@router.get("/{dashboard_id}", response_model=DashboardOut)
def get_dashboard(
    dashboard_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dashboard = _apply_visibility(db.query(Dashboard), current_user).filter(Dashboard.id == dashboard_id).first()
    if not dashboard:
        raise HTTPException(status_code=404, detail="看板不存在")
    return dashboard


@router.put("/{dashboard_id}", response_model=DashboardOut)
def update_dashboard(
    dashboard_id: int,
    payload: DashboardUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dashboard = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
    if not dashboard:
        raise HTTPException(status_code=404, detail="看板不存在")
    if not _can_manage_dashboard(current_user, dashboard):
        raise HTTPException(status_code=403, detail="无权限")
    values = payload.model_dump(exclude_unset=True)
    _ensure_dashboard_values(values.get("status"), values.get("visibility"))
    for key, value in values.items():
        setattr(dashboard, key, value)
    if values:
        dashboard.version = (dashboard.version or 1) + 1
    if dashboard.status == "published":
        _sync_dashboard_asset(db, dashboard)
    db.commit()
    db.refresh(dashboard)
    try_record_audit_log(
        db,
        actor=current_user,
        action="dashboard.update",
        resource_type="dashboard",
        resource_id=dashboard.id,
        resource_name=dashboard.title,
        org_id=dashboard.org_id,
        message="看板已更新",
        detail={"fields": list(values.keys())},
    )
    return dashboard


@router.put("/{dashboard_id}/share", response_model=DashboardOut)
def share_dashboard(
    dashboard_id: int,
    payload: DashboardShareUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dashboard = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
    if not dashboard:
        raise HTTPException(status_code=404, detail="看板不存在")
    if not _can_manage_dashboard(current_user, dashboard):
        raise HTTPException(status_code=403, detail="无权限")

    was_public = bool(dashboard.is_public)
    dashboard.is_public = 1 if payload.is_public else 0
    dashboard.shared_user_ids = payload.shared_user_ids or []
    if dashboard.is_public and not dashboard.share_token:
        dashboard.share_token = secrets.token_urlsafe(24)
    if not dashboard.is_public:
        dashboard.share_token = None
    db.commit()
    db.refresh(dashboard)
    try_record_audit_log(
        db,
        actor=current_user,
        action="dashboard.share",
        resource_type="dashboard",
        resource_id=dashboard.id,
        resource_name=dashboard.title,
        org_id=dashboard.org_id,
        message="看板分享配置已更新",
        detail={
            "is_public": bool(dashboard.is_public),
            "shared_user_ids": dashboard.shared_user_ids,
        },
    )
    _safe_dispatch_dashboard_event(
        db,
        MessageEvent(
            event_type="dashboard.shared",
            org_id=dashboard.org_id,
            recipient_user_ids=_shared_recipients(dashboard.shared_user_ids, current_user.id),
            title=f"看板分享：{dashboard.title}",
            content=f"{current_user.username} 分享了看板「{dashboard.title}」。",
            link_url=f"/dashboard-center?dashboard_id={dashboard.id}",
        ),
    )
    if dashboard.is_public and not was_public:
        dispatch_event(
            db,
            dashboard.org_id,
            "dashboard.published",
            {
                "dashboard_id": dashboard.id,
                "title": dashboard.title,
                "version": dashboard.version,
                "is_public": True,
                "share_token": dashboard.share_token,
            },
        )
    return dashboard


@router.post("/{dashboard_id}/publish", response_model=DashboardOut)
def publish_dashboard(
    dashboard_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dashboard = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
    if not dashboard:
        raise HTTPException(status_code=404, detail="看板不存在")
    if not _can_manage_dashboard(current_user, dashboard):
        raise HTTPException(status_code=403, detail="无权限")
    dashboard.status = "published"
    dashboard.visibility = "org"
    _sync_dashboard_asset(db, dashboard)
    db.commit()
    db.refresh(dashboard)
    try_record_audit_log(
        db,
        actor=current_user,
        action="dashboard.publish",
        resource_type="dashboard",
        resource_id=dashboard.id,
        resource_name=dashboard.title,
        org_id=dashboard.org_id,
        message="看板已发布",
    )
    dispatch_event(
        db,
        dashboard.org_id,
        "dashboard.published",
        {"dashboard_id": dashboard.id, "title": dashboard.title, "version": dashboard.version},
    )
    return dashboard


@router.delete("/{dashboard_id}")
def delete_dashboard(
    dashboard_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dashboard = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
    if not dashboard:
        raise HTTPException(status_code=404, detail="看板不存在")
    if not _can_manage_dashboard(current_user, dashboard):
        raise HTTPException(status_code=403, detail="无权限")
    assert_dashboard_can_delete(db, dashboard)
    dashboard_id_value = dashboard.id
    dashboard_title = dashboard.title
    dashboard_org_id = dashboard.org_id
    delete_catalog_asset(db, "dashboard", dashboard.id)
    db.delete(dashboard)
    db.commit()
    try_record_audit_log(
        db,
        actor=current_user,
        action="dashboard.delete",
        resource_type="dashboard",
        resource_id=dashboard_id_value,
        resource_name=dashboard_title,
        org_id=dashboard_org_id,
        message="看板已删除",
    )
    return {"status": "ok"}
