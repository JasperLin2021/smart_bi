from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.audit import try_record_audit_log
from app.core.tenant_limits import assert_can_create_resource
from app.db.session import get_db
from app.models.big_screen import BigScreen
from app.models.catalog import DataAsset
from app.models.user import User
from app.schemas.big_screen import (
    BigScreenCreate,
    BigScreenListResponse,
    BigScreenOut,
    BigScreenUpdate,
)

router = APIRouter(prefix="/big-screens", tags=["big_screens"])

VALID_BIG_SCREEN_STATUSES = {"draft", "published", "archived"}
VALID_VISIBILITIES = {"private", "org"}


def _ensure_values(status: str | None = None, visibility: str | None = None) -> None:
    if status is not None and status not in VALID_BIG_SCREEN_STATUSES:
        raise HTTPException(status_code=400, detail="无效大屏状态")
    if visibility is not None and visibility not in VALID_VISIBILITIES:
        raise HTTPException(status_code=400, detail="无效可见范围")


def _can_manage(user: User, screen: BigScreen) -> bool:
    if user.role == "super_admin":
        return True
    if user.role == "org_admin" and screen.org_id == user.org_id:
        return True
    return screen.owner_id == user.id


def _apply_visibility(query, user: User):
    if user.role == "super_admin":
        return query
    query = query.filter(BigScreen.org_id == user.org_id)
    if user.role == "org_admin":
        return query
    return query.filter(or_(BigScreen.status == "published", BigScreen.owner_id == user.id))


def _sync_big_screen_asset(db: Session, screen: BigScreen) -> None:
    asset = (
        db.query(DataAsset)
        .filter(DataAsset.asset_type == "big_screen", DataAsset.asset_id == screen.id)
        .first()
    )
    if not asset:
        asset = DataAsset(asset_type="big_screen", asset_id=screen.id)
        db.add(asset)
    asset.name = screen.title
    asset.description = screen.description
    asset.org_id = screen.org_id
    asset.owner_id = screen.owner_id
    asset.status = screen.status
    asset.metadata_json = {
        "visibility": screen.visibility,
        "widget_count": len((screen.canvas_json or {}).get("widgets", [])),
    }


@router.get("", response_model=BigScreenListResponse)
def list_big_screens(
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = _apply_visibility(db.query(BigScreen), current_user)
    if status:
        query = query.filter(BigScreen.status == status)
    return {"items": query.order_by(BigScreen.id.desc()).all()}


@router.post("", response_model=BigScreenOut)
def create_big_screen(
    payload: BigScreenCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_values(payload.status, payload.visibility)
    org_id = payload.org_id if current_user.role == "super_admin" and payload.org_id else current_user.org_id
    assert_can_create_resource(db, org_id, "big_screens")
    screen = BigScreen(
        **payload.model_dump(exclude={"org_id", "owner_id"}),
        org_id=org_id,
        owner_id=payload.owner_id or current_user.id,
    )
    db.add(screen)
    db.flush()
    if screen.status == "published":
        _sync_big_screen_asset(db, screen)
    db.commit()
    db.refresh(screen)
    try_record_audit_log(
        db,
        actor=current_user,
        action="big_screen.create",
        resource_type="big_screen",
        resource_id=screen.id,
        resource_name=screen.title,
        org_id=screen.org_id,
        message="大屏已创建",
        detail={"status": screen.status, "visibility": screen.visibility},
    )
    return screen


@router.get("/{screen_id}", response_model=BigScreenOut)
def get_big_screen(
    screen_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    screen = _apply_visibility(db.query(BigScreen), current_user).filter(BigScreen.id == screen_id).first()
    if not screen:
        raise HTTPException(status_code=404, detail="大屏不存在")
    return screen


@router.put("/{screen_id}", response_model=BigScreenOut)
def update_big_screen(
    screen_id: int,
    payload: BigScreenUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    screen = db.query(BigScreen).filter(BigScreen.id == screen_id).first()
    if not screen:
        raise HTTPException(status_code=404, detail="大屏不存在")
    if not _can_manage(current_user, screen):
        raise HTTPException(status_code=403, detail="无权限")
    values = payload.model_dump(exclude_unset=True)
    _ensure_values(values.get("status"), values.get("visibility"))
    for key, value in values.items():
        setattr(screen, key, value)
    if screen.status == "published":
        _sync_big_screen_asset(db, screen)
    db.commit()
    db.refresh(screen)
    try_record_audit_log(
        db,
        actor=current_user,
        action="big_screen.update",
        resource_type="big_screen",
        resource_id=screen.id,
        resource_name=screen.title,
        org_id=screen.org_id,
        message="大屏已更新",
        detail={"fields": list(values.keys())},
    )
    return screen


@router.post("/{screen_id}/publish", response_model=BigScreenOut)
def publish_big_screen(
    screen_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    screen = db.query(BigScreen).filter(BigScreen.id == screen_id).first()
    if not screen:
        raise HTTPException(status_code=404, detail="大屏不存在")
    if not _can_manage(current_user, screen):
        raise HTTPException(status_code=403, detail="无权限")
    screen.status = "published"
    screen.visibility = "org"
    _sync_big_screen_asset(db, screen)
    db.commit()
    db.refresh(screen)
    try_record_audit_log(
        db,
        actor=current_user,
        action="big_screen.publish",
        resource_type="big_screen",
        resource_id=screen.id,
        resource_name=screen.title,
        org_id=screen.org_id,
        message="大屏已发布",
    )
    return screen


@router.delete("/{screen_id}")
def delete_big_screen(
    screen_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    screen = db.query(BigScreen).filter(BigScreen.id == screen_id).first()
    if not screen:
        raise HTTPException(status_code=404, detail="大屏不存在")
    if not _can_manage(current_user, screen):
        raise HTTPException(status_code=403, detail="无权限")
    screen_title = screen.title
    screen_org_id = screen.org_id
    db.query(DataAsset).filter(DataAsset.asset_type == "big_screen", DataAsset.asset_id == screen.id).delete()
    db.delete(screen)
    db.commit()
    try_record_audit_log(
        db,
        actor=current_user,
        action="big_screen.delete",
        resource_type="big_screen",
        resource_id=screen_id,
        resource_name=screen_title,
        org_id=screen_org_id,
        message="大屏已删除",
    )
    return {"status": "ok"}
