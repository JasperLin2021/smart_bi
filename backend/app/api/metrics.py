from datetime import datetime

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

VALID_METRIC_STATUSES = {"draft", "published", "archived"}
VALID_CERTIFICATION_STATUSES = {"draft", "pending_review", "certified", "deprecated"}
VALID_QUALITY_STATUSES = {"unknown", "normal", "stale", "error"}


def ensure_admin(user: User):
    if user.role != "super_admin":
        raise HTTPException(status_code=403, detail="无权限")


def _get_datasource_or_404(db: Session, datasource_id: int) -> DataSource:
    datasource = db.query(DataSource).filter(DataSource.id == datasource_id).first()
    if not datasource:
        raise HTTPException(status_code=404, detail="数据源不存在")
    return datasource


def _ensure_metric_values(status: str | None = None, certification_status: str | None = None, quality_status: str | None = None) -> None:
    if status is not None and status not in VALID_METRIC_STATUSES:
        raise HTTPException(status_code=400, detail="无效指标发布状态")
    if certification_status is not None and certification_status not in VALID_CERTIFICATION_STATUSES:
        raise HTTPException(status_code=400, detail="无效指标认证状态")
    if quality_status is not None and quality_status not in VALID_QUALITY_STATUSES:
        raise HTTPException(status_code=400, detail="无效指标质量状态")


def _apply_metric_visibility(query, user: User):
    if user.role == "super_admin":
        return query
    return query.join(DataSource, Metric.datasource_id == DataSource.id).filter(DataSource.org_id == user.org_id)


def _touch_certification(metric: Metric, current_user: User, previous_status: str | None = None) -> None:
    if metric.certification_status != "certified":
        return
    if previous_status == "certified" and metric.certified_at:
        return
    metric.certified_by = getattr(current_user, "username", None) or getattr(current_user, "name", None)
    metric.certified_at = datetime.utcnow()


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
        "certification_status": metric.certification_status,
        "certified_by": metric.certified_by,
        "certified_at": metric.certified_at.isoformat() if metric.certified_at else None,
        "caliber_version": metric.caliber_version,
        "data_updated_at": metric.data_updated_at.isoformat() if metric.data_updated_at else None,
        "quality_status": metric.quality_status,
        "quality_message": metric.quality_message,
        "lineage": metric.lineage_json,
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
    query = _apply_metric_visibility(db.query(Metric), current_user)
    items = query.order_by(Metric.updated_at.desc(), Metric.id.desc()).all()
    return {"items": items}


@router.post("", response_model=MetricOut)
def create_metric(
    payload: MetricCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_admin(current_user)
    _ensure_metric_values(payload.status, payload.certification_status, payload.quality_status)
    datasource = _get_datasource_or_404(db, payload.datasource_id)
    existing = db.query(Metric).filter(Metric.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="指标名称已存在")
    metric = Metric(**payload.model_dump())
    _touch_certification(metric, current_user)
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
    if current_user.role != "super_admin":
        datasource = db.query(DataSource).filter(DataSource.id == metric.datasource_id).first()
        if not datasource or datasource.org_id != current_user.org_id:
            raise HTTPException(status_code=404, detail="指标不存在")
    return metric


@router.get("/{metric_id}/lineage")
def get_metric_lineage(
    metric_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    metric = get_metric(metric_id, db=db, current_user=current_user)
    datasource = (
        db.query(DataSource).filter(DataSource.id == metric.datasource_id).first()
        if metric.datasource_id
        else None
    )
    return {
        "metric": {
            "id": metric.id,
            "name": metric.name,
            "definition": metric.definition,
            "formula": metric.formula,
            "unit": metric.unit,
            "aggregation": metric.aggregation,
            "caliber_version": metric.caliber_version,
        },
        "datasource": {
            "id": datasource.id if datasource else None,
            "name": datasource.name if datasource else None,
            "source_type": datasource.source_type if datasource else None,
        },
        "source": {
            "table_name": metric.table_name,
            "column_name": metric.column_name,
            "lineage": metric.lineage_json,
        },
        "trust": {
            "certification_status": metric.certification_status,
            "certified_by": metric.certified_by,
            "certified_at": metric.certified_at,
            "quality_status": metric.quality_status,
            "quality_message": metric.quality_message,
            "data_updated_at": metric.data_updated_at,
        },
        "usage": {
            "catalog_asset": "metric",
            "datasource_id": metric.datasource_id,
        },
    }


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
    values = payload.model_dump(exclude_unset=True)
    _ensure_metric_values(
        values.get("status"),
        values.get("certification_status"),
        values.get("quality_status"),
    )
    previous_certification_status = metric.certification_status
    for key, value in values.items():
        setattr(metric, key, value)
    _touch_certification(metric, current_user, previous_status=previous_certification_status)
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
