from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.catalog import DataAsset
from app.models.user import User
from app.schemas.catalog import (
    DataAssetCreate,
    DataAssetListResponse,
    DataAssetOut,
    DataAssetStatusUpdate,
    DataAssetUpdate,
)

router = APIRouter(prefix="/catalog", tags=["catalog"])

VALID_ASSET_STATUSES = {"draft", "published", "archived"}


def _ensure_status(status: str) -> None:
    if status not in VALID_ASSET_STATUSES:
        raise HTTPException(status_code=400, detail="无效资产状态")


def _can_manage_asset(user: User, asset: DataAsset) -> bool:
    if user.role == "super_admin":
        return True
    if user.role == "org_admin" and asset.org_id == user.org_id:
        return True
    return asset.owner_id == user.id


def _apply_visibility(query, user: User):
    if user.role == "super_admin":
        return query

    query = query.filter(DataAsset.org_id == user.org_id)
    if user.role == "org_admin":
        return query

    return query.filter(or_(DataAsset.status == "published", DataAsset.owner_id == user.id))


@router.get("/assets", response_model=DataAssetListResponse)
def list_assets(
    q: str | None = None,
    asset_type: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = _apply_visibility(db.query(DataAsset), current_user)
    if q:
        query = query.filter(DataAsset.name.ilike(f"%{q}%"))
    if asset_type:
        query = query.filter(DataAsset.asset_type == asset_type)
    if status:
        query = query.filter(DataAsset.status == status)
    return {"items": query.order_by(DataAsset.id.desc()).all()}


@router.post("/assets", response_model=DataAssetOut)
def create_asset(
    payload: DataAssetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("org_admin", "super_admin"):
        raise HTTPException(status_code=403, detail="无权限")
    _ensure_status(payload.status)
    org_id = payload.org_id if current_user.role == "super_admin" else current_user.org_id
    asset = DataAsset(
        **payload.model_dump(exclude={"org_id", "owner_id"}),
        org_id=org_id,
        owner_id=payload.owner_id or current_user.id,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


@router.get("/assets/{asset_id}", response_model=DataAssetOut)
def get_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    asset = _apply_visibility(db.query(DataAsset), current_user).filter(DataAsset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="数据资产不存在")
    return asset


@router.put("/assets/{asset_id}", response_model=DataAssetOut)
def update_asset(
    asset_id: int,
    payload: DataAssetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    asset = db.query(DataAsset).filter(DataAsset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="数据资产不存在")
    if not _can_manage_asset(current_user, asset):
        raise HTTPException(status_code=403, detail="无权限")
    values = payload.model_dump(exclude_unset=True)
    if "status" in values:
        _ensure_status(values["status"])
    for key, value in values.items():
        setattr(asset, key, value)
    db.commit()
    db.refresh(asset)
    return asset


@router.put("/assets/{asset_id}/status", response_model=DataAssetOut)
def update_asset_status(
    asset_id: int,
    payload: DataAssetStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_status(payload.status)
    asset = db.query(DataAsset).filter(DataAsset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="数据资产不存在")
    if not _can_manage_asset(current_user, asset):
        raise HTTPException(status_code=403, detail="无权限")
    asset.status = payload.status
    db.commit()
    db.refresh(asset)
    return asset
