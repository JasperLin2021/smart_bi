from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.auth import get_current_user
from app.db.session import get_db
from app.core.audit import try_record_audit_log
from app.models.catalog import DataAsset
from app.models.datasource import DataSource
from app.models.metric import Metric
from app.models.user import User
from app.schemas.metric import MetricCreate, MetricUpdate, MetricOut, MetricListResponse
from app.core.metric_formula import generate_metric_formula
from app.core.metric_prompt_sync import sync_datasource_metrics_prompt

router = APIRouter(prefix="/metrics", tags=["metrics"])


def ensure_admin(user: User):
    if user.role != "super_admin":
        raise HTTPException(status_code=403, detail="无权限")


def _get_datasource_or_404(db: Session, datasource_id: int) -> DataSource:
    datasource = db.query(DataSource).filter(DataSource.id == datasource_id).first()
    if not datasource:
        raise HTTPException(status_code=404, detail="数据源不存在")
    return datasource


def _supports_catalog_sync(db: Session) -> bool:
    return hasattr(db, "get_bind") and hasattr(db, "flush")


def _sync_metric_catalog_asset(db: Session, metric: Metric, datasource: DataSource | None = None) -> None:
    if not _supports_catalog_sync(db):
        return

    datasource = datasource or (
        db.query(DataSource).filter(DataSource.id == metric.datasource_id).first()
        if metric.datasource_id
        else None
    )
    asset = (
        db.query(DataAsset)
        .filter(DataAsset.asset_type == "metric", DataAsset.asset_id == metric.id)
        .first()
    )
    if not asset:
        asset = DataAsset(asset_type="metric", asset_id=metric.id, name=metric.name)
        db.add(asset)

    asset.name = metric.name
    asset.description = metric.description or metric.definition
    asset.datasource_id = metric.datasource_id
    asset.org_id = datasource.org_id if datasource else None
    asset.status = metric.status or "draft"
    asset.tags = metric.tags
    asset.metadata_json = {
        "definition": metric.definition,
        "formula": metric.formula,
        "table_name": metric.table_name,
        "column_name": metric.column_name,
        "owner_name": metric.owner_name,
        "unit": metric.unit,
        "aggregation": metric.aggregation,
        "dimensions": metric.dimensions,
        "is_active": metric.is_active,
    }
    db.flush()


def _delete_metric_catalog_asset(db: Session, metric_id: int) -> None:
    if not _supports_catalog_sync(db):
        return
    asset = (
        db.query(DataAsset)
        .filter(DataAsset.asset_type == "metric", DataAsset.asset_id == metric_id)
        .first()
    )
    if asset:
        db.delete(asset)


def _record_metric_audit(db: Session, current_user: User, action: str, metric: Metric | None = None, **extra) -> None:
    if not _supports_catalog_sync(db):
        return
    try_record_audit_log(
        db,
        actor=current_user,
        action=action,
        resource_type="metric",
        resource_id=getattr(metric, "id", extra.get("resource_id")),
        resource_name=getattr(metric, "name", extra.get("resource_name")),
        org_id=extra.get("org_id"),
        message=extra.get("message"),
        detail=extra.get("detail"),
    )


@router.get("", response_model=MetricListResponse)
def list_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = db.query(Metric).order_by(Metric.updated_at.desc()).all()
    return {"items": items}


@router.post("", response_model=MetricOut)
def create_metric(
    payload: MetricCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_admin(current_user)
    datasource = _get_datasource_or_404(db, payload.datasource_id)
    existing = db.query(Metric).filter(Metric.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="指标名称已存在")
    metric = Metric(**payload.model_dump())
    db.add(metric)
    db.commit()
    db.refresh(metric)
    _sync_metric_catalog_asset(db, metric, datasource)
    sync_datasource_metrics_prompt(db, payload.datasource_id)
    db.commit()
    db.refresh(metric)
    _record_metric_audit(
        db,
        current_user,
        "metric.create",
        metric,
        org_id=getattr(datasource, "org_id", None),
        message="指标已创建",
        detail={"datasource_id": metric.datasource_id, "status": metric.status},
    )
    return metric


@router.get("/{metric_id}", response_model=MetricOut)
def get_metric(
    metric_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    metric = db.query(Metric).filter(Metric.id == metric_id).first()
    if not metric:
        raise HTTPException(status_code=404, detail="指标不存在")
    return metric


@router.put("/{metric_id}", response_model=MetricOut)
def update_metric(
    metric_id: int,
    payload: MetricUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_admin(current_user)
    metric = db.query(Metric).filter(Metric.id == metric_id).first()
    if not metric:
        raise HTTPException(status_code=404, detail="指标不存在")
    previous_datasource_id = metric.datasource_id
    previous_datasource = (
        db.query(DataSource).filter(DataSource.id == previous_datasource_id).first()
        if previous_datasource_id
        else None
    )
    if payload.datasource_id is not None:
        _get_datasource_or_404(db, payload.datasource_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(metric, key, value)
    db.commit()
    db.refresh(metric)
    current_datasource = (
        db.query(DataSource).filter(DataSource.id == metric.datasource_id).first()
        if metric.datasource_id
        else previous_datasource
    )
    _sync_metric_catalog_asset(db, metric, current_datasource)
    if previous_datasource_id:
        sync_datasource_metrics_prompt(db, previous_datasource_id)
    if metric.datasource_id and metric.datasource_id != previous_datasource_id:
        sync_datasource_metrics_prompt(db, metric.datasource_id)
    elif metric.datasource_id:
        sync_datasource_metrics_prompt(db, metric.datasource_id)
    db.commit()
    db.refresh(metric)
    _record_metric_audit(
        db,
        current_user,
        "metric.update",
        metric,
        org_id=current_datasource.org_id if current_datasource else None,
        message="指标已更新",
        detail={"fields": list(payload.model_dump(exclude_unset=True).keys())},
    )
    return metric


@router.post("/generate-formula")
async def generate_formula(
    payload: MetricCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_admin(current_user)
    datasource = _get_datasource_or_404(db, payload.datasource_id)
    formula = await generate_metric_formula(
        datasource_context={
            "name": datasource.name,
            "metadata_prompt": datasource.metadata_prompt,
            "schema_metadata": datasource.schema_metadata,
        },
        name=payload.name,
        definition=payload.definition,
        table_name=payload.table_name,
        column_name=payload.column_name,
    )
    return {"formula": formula}


@router.delete("/{metric_id}")
def delete_metric(
    metric_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_admin(current_user)
    metric = db.query(Metric).filter(Metric.id == metric_id).first()
    if not metric:
        raise HTTPException(status_code=404, detail="指标不存在")
    datasource_id = metric.datasource_id
    metric_id = metric.id
    metric_name = metric.name
    datasource = db.query(DataSource).filter(DataSource.id == datasource_id).first() if datasource_id else None
    _delete_metric_catalog_asset(db, metric_id)
    db.delete(metric)
    db.commit()
    if datasource_id:
        sync_datasource_metrics_prompt(db, datasource_id)
        db.commit()
    _record_metric_audit(
        db,
        current_user,
        "metric.delete",
        None,
        resource_id=metric_id,
        resource_name=metric_name,
        org_id=datasource.org_id if datasource else None,
        message="指标已删除",
    )
    return {"status": "ok"}
