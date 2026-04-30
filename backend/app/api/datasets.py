from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.audit import try_record_audit_log
from app.db.session import get_db
from app.models.catalog import DataAsset
from app.models.dataset import Dataset
from app.models.datasource import DataSource
from app.models.user import User
from app.schemas.dataset import DatasetCreate, DatasetListResponse, DatasetOut, DatasetUpdate

router = APIRouter(prefix="/datasets", tags=["datasets"])

VALID_DATASET_STATUSES = {"draft", "published", "archived"}
VALID_VISIBILITIES = {"private", "org"}


def _ensure_values(status: str | None = None, visibility: str | None = None) -> None:
    if status is not None and status not in VALID_DATASET_STATUSES:
        raise HTTPException(status_code=400, detail="无效数据集状态")
    if visibility is not None and visibility not in VALID_VISIBILITIES:
        raise HTTPException(status_code=400, detail="无效可见范围")


def _get_datasource_for_user(db: Session, datasource_id: int, user: User) -> DataSource:
    datasource = db.query(DataSource).filter(DataSource.id == datasource_id).first()
    if not datasource:
        raise HTTPException(status_code=404, detail="数据源不存在")
    if user.role != "super_admin" and datasource.org_id != user.org_id:
        raise HTTPException(status_code=403, detail="无权访问此数据源")
    return datasource


def _can_manage_dataset(user: User, dataset: Dataset) -> bool:
    if user.role == "super_admin":
        return True
    if user.role == "org_admin" and dataset.org_id == user.org_id:
        return True
    return dataset.owner_id == user.id


def _apply_visibility(query, user: User):
    if user.role == "super_admin":
        return query
    query = query.filter(Dataset.org_id == user.org_id)
    if user.role == "org_admin":
        return query
    return query.filter(or_(Dataset.status == "published", Dataset.owner_id == user.id))


def _sync_dataset_asset(db: Session, dataset: Dataset) -> None:
    asset = (
        db.query(DataAsset)
        .filter(DataAsset.asset_type == "dataset", DataAsset.asset_id == dataset.id)
        .first()
    )
    if not asset:
        asset = DataAsset(asset_type="dataset", asset_id=dataset.id)
        db.add(asset)
    asset.name = dataset.name
    asset.description = dataset.description
    asset.datasource_id = dataset.datasource_id
    asset.org_id = dataset.org_id
    asset.owner_id = dataset.owner_id
    asset.status = dataset.status
    asset.metadata_json = {
        "visibility": dataset.visibility,
        "fields": dataset.fields_json,
        "filters": dataset.filters_json,
        "derived_columns": dataset.derived_columns_json,
        "joins": dataset.joins_json,
        "aggregations": dataset.aggregations_json,
    }


@router.get("", response_model=DatasetListResponse)
def list_datasets(
    status: str | None = None,
    datasource_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = _apply_visibility(db.query(Dataset), current_user)
    if status:
        query = query.filter(Dataset.status == status)
    if datasource_id:
        query = query.filter(Dataset.datasource_id == datasource_id)
    return {"items": query.order_by(Dataset.id.desc()).all()}


@router.post("", response_model=DatasetOut)
def create_dataset(
    payload: DatasetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_values(payload.status, payload.visibility)
    datasource = _get_datasource_for_user(db, payload.datasource_id, current_user)
    org_id = payload.org_id if current_user.role == "super_admin" and payload.org_id else datasource.org_id
    dataset = Dataset(
        **payload.model_dump(exclude={"org_id", "owner_id"}),
        org_id=org_id,
        owner_id=payload.owner_id or current_user.id,
    )
    db.add(dataset)
    db.flush()
    if dataset.status == "published":
        _sync_dataset_asset(db, dataset)
    db.commit()
    db.refresh(dataset)
    try_record_audit_log(
        db,
        actor=current_user,
        action="dataset.create",
        resource_type="dataset",
        resource_id=dataset.id,
        resource_name=dataset.name,
        org_id=dataset.org_id,
        message="数据集已创建",
        detail={"datasource_id": dataset.datasource_id, "status": dataset.status},
    )
    return dataset


@router.get("/{dataset_id}", response_model=DatasetOut)
def get_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = _apply_visibility(db.query(Dataset), current_user).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")
    return dataset


@router.put("/{dataset_id}", response_model=DatasetOut)
def update_dataset(
    dataset_id: int,
    payload: DatasetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")
    if not _can_manage_dataset(current_user, dataset):
        raise HTTPException(status_code=403, detail="无权限")
    values = payload.model_dump(exclude_unset=True)
    _ensure_values(values.get("status"), values.get("visibility"))
    if "datasource_id" in values:
        datasource = _get_datasource_for_user(db, values["datasource_id"], current_user)
        if current_user.role != "super_admin":
            dataset.org_id = datasource.org_id
    for key, value in values.items():
        setattr(dataset, key, value)
    if dataset.status == "published":
        _sync_dataset_asset(db, dataset)
    db.commit()
    db.refresh(dataset)
    try_record_audit_log(
        db,
        actor=current_user,
        action="dataset.update",
        resource_type="dataset",
        resource_id=dataset.id,
        resource_name=dataset.name,
        org_id=dataset.org_id,
        message="数据集已更新",
        detail={"fields": list(values.keys())},
    )
    return dataset


@router.post("/{dataset_id}/publish", response_model=DatasetOut)
def publish_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")
    if not _can_manage_dataset(current_user, dataset):
        raise HTTPException(status_code=403, detail="无权限")
    dataset.status = "published"
    dataset.visibility = "org"
    _sync_dataset_asset(db, dataset)
    db.commit()
    db.refresh(dataset)
    try_record_audit_log(
        db,
        actor=current_user,
        action="dataset.publish",
        resource_type="dataset",
        resource_id=dataset.id,
        resource_name=dataset.name,
        org_id=dataset.org_id,
        message="数据集已发布",
    )
    return dataset


@router.delete("/{dataset_id}")
def delete_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")
    if not _can_manage_dataset(current_user, dataset):
        raise HTTPException(status_code=403, detail="无权限")
    dataset_name = dataset.name
    dataset_org_id = dataset.org_id
    db.query(DataAsset).filter(DataAsset.asset_type == "dataset", DataAsset.asset_id == dataset.id).delete()
    db.delete(dataset)
    db.commit()
    try_record_audit_log(
        db,
        actor=current_user,
        action="dataset.delete",
        resource_type="dataset",
        resource_id=dataset_id,
        resource_name=dataset_name,
        org_id=dataset_org_id,
        message="数据集已删除",
    )
    return {"status": "ok"}
