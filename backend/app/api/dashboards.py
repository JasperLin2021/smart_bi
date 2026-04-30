import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.audit import try_record_audit_log
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


@router.get("/public/{share_token}", response_model=DashboardOut)
def get_public_dashboard(
    share_token: str,
    db: Session = Depends(get_db),
):
    dashboard = (
        db.query(Dashboard)
        .filter(Dashboard.share_token == share_token, Dashboard.is_public == 1)
        .first()
    )
    if not dashboard:
        raise HTTPException(status_code=404, detail="公开看板不存在")
    return dashboard


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
    dashboard_id_value = dashboard.id
    dashboard_title = dashboard.title
    dashboard_org_id = dashboard.org_id
    db.query(DataAsset).filter(DataAsset.asset_type == "dashboard", DataAsset.asset_id == dashboard.id).delete()
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
