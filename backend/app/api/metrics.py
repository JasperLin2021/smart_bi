from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.auth import get_current_user
from app.db.session import get_db
from app.core.audit import try_record_audit_log
from app.core.permissions import has_action_permission, require_org_admin_or_above
from app.core.safe_delete import assert_metric_can_delete, delete_catalog_asset
from app.models.catalog import DataAsset
from app.models.datasource import DataSource
from app.models.dataset import Dataset
from app.models.metric import Metric
from app.models.organization import Organization
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


def _get_dataset_or_404(db: Session, dataset_id: int) -> Dataset:
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")
    return dataset


def _resolve_dataset_binding(db: Session, dataset_id: int) -> tuple[Dataset, DataSource]:
    dataset = _get_dataset_or_404(db, dataset_id)
    datasource = _get_datasource_or_404(db, dataset.datasource_id)
    return dataset, datasource


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


def _certifier_can_certify(user: User) -> bool:
    return has_action_permission(user, "metric.certify")


def _validate_metric_certifier(db: Session, certified_by: str | None, datasource: DataSource | None) -> str | None:
    if not certified_by:
        return None
    certifier = db.query(User).filter(User.username == certified_by).first()
    if not certifier:
        raise HTTPException(status_code=400, detail="认证人不存在")
    if not _certifier_can_certify(certifier):
        raise HTTPException(status_code=400, detail="认证人没有指标认证权限")
    if datasource and datasource.org_id and certifier.role != "super_admin" and certifier.org_id != datasource.org_id:
        raise HTTPException(status_code=400, detail="认证人不属于指标所在企业")
    return certifier.username


def _touch_certification(
    metric: Metric,
    current_user: User,
    previous_status: str | None = None,
    previous_certified_by: str | None = None,
) -> None:
    if metric.certification_status != "certified":
        return
    if previous_status == "certified" and metric.certified_at and metric.certified_by == previous_certified_by:
        return
    if not metric.certified_by:
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
        "is_active": metric.is_active,
    }
    db.flush()


def _delete_metric_catalog_asset(db: Session, metric_id: int) -> None:
    if not _supports_catalog_sync(db):
        return
    delete_catalog_asset(db, "metric", metric_id)


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


@router.get("/certifiers")
def list_metric_certifiers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_org_admin_or_above(current_user)
    query = db.query(User)
    if current_user.role != "super_admin":
        query = query.filter(User.org_id == current_user.org_id)
    users = query.order_by(User.org_id, User.username).all()
    org_ids = {user.org_id for user in users if user.org_id}
    orgs = (
        db.query(Organization).filter(Organization.id.in_(org_ids)).all()
        if org_ids
        else []
    )
    org_names = {org.id: org.name for org in orgs}
    items = []
    for user in users:
        if not _certifier_can_certify(user):
            continue
        items.append(
            {
                "id": user.id,
                "username": user.username,
                "role": user.role,
                "department": getattr(user, "department", None),
                "org_id": user.org_id,
                "org_name": org_names.get(user.org_id),
                "can_certify_metric": True,
            }
        )
    return {"items": items}


@router.post("", response_model=MetricOut)
def create_metric(
    payload: MetricCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_admin(current_user)
    _ensure_metric_values(payload.status, payload.certification_status, payload.quality_status)
    _dataset, datasource = _resolve_dataset_binding(db, payload.dataset_id)
    existing = db.query(Metric).filter(Metric.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="指标名称已存在")
    data = payload.model_dump()
    data["datasource_id"] = datasource.id
    data["certified_by"] = _validate_metric_certifier(db, data.get("certified_by"), datasource)
    metric = Metric(**data)
    _touch_certification(metric, current_user)
    db.add(metric)
    db.commit()
    db.refresh(metric)
    _sync_metric_catalog_asset(db, metric, datasource)
    sync_datasource_metrics_prompt(db, datasource.id)
    db.commit()
    db.refresh(metric)
    _record_metric_audit(
        db,
        current_user,
        "metric.create",
        metric,
        org_id=getattr(datasource, "org_id", None),
        message="指标已创建",
        detail={"dataset_id": metric.dataset_id, "datasource_id": metric.datasource_id, "status": metric.status},
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
    dataset = (
        db.query(Dataset).filter(Dataset.id == metric.dataset_id).first()
        if metric.dataset_id
        else None
    )

    # Build dataset lineage info from fields_json (single source of truth)
    fields_json = (dataset.fields_json or {}) if dataset else {}
    main_table = str(fields_json.get("table") or "")
    raw_fields = fields_json.get("dimensions") or fields_json.get("fields") or []
    raw_joins = fields_json.get("joins") or []

    def _fname(f):
        return f["name"] if isinstance(f, dict) else str(f)

    dataset_fields = [
        {"name": _fname(f), "label": f.get("label", "") if isinstance(f, dict) else "", "type": f.get("type", "") if isinstance(f, dict) else ""}
        for f in raw_fields
    ]

    dataset_joins = []
    for item in raw_joins:
        if isinstance(item, dict):
            dataset_joins.append({
                "table": str(item.get("right") or item.get("table") or ""),
                "join_type": str(item.get("type") or "JOIN"),
                "join_on": str(item.get("on") or item.get("condition") or ""),
            })
        elif isinstance(item, str):
            dataset_joins.append({"table": item, "join_type": "JOIN", "join_on": ""})

    return {
        "metric": {
            "id": metric.id,
            "name": metric.name,
            "definition": metric.definition,
            "formula": metric.formula,
            "unit": metric.unit,
            "aggregation": metric.aggregation,
            "caliber_version": metric.caliber_version,
            "owner_name": metric.owner_name,
        },
        "dataset": {
            "id": dataset.id if dataset else None,
            "name": dataset.name if dataset else None,
            "description": dataset.description if dataset else None,
            "main_table": main_table or None,
            "fields": dataset_fields,
            "joins": dataset_joins,
        },
        "datasource": {
            "id": datasource.id if datasource else None,
            "name": datasource.name if datasource else None,
            "source_type": datasource.source_type if datasource else None,
        },
        "source": {
            "table_name": main_table or None,
            "column_name": metric.column_name,
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
    values = payload.model_dump(exclude_unset=True)
    if "dataset_id" in values:
        _dataset, previous_datasource = _resolve_dataset_binding(db, values["dataset_id"])
        values["datasource_id"] = previous_datasource.id
    _ensure_metric_values(
        values.get("status"),
        values.get("certification_status"),
        values.get("quality_status"),
    )
    previous_certification_status = metric.certification_status
    previous_certified_by = metric.certified_by
    if "certified_by" in values:
        values["certified_by"] = _validate_metric_certifier(db, values.get("certified_by"), previous_datasource)
    for key, value in values.items():
        setattr(metric, key, value)
    _touch_certification(
        metric,
        current_user,
        previous_status=previous_certification_status,
        previous_certified_by=previous_certified_by,
    )
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
    _dataset, datasource = _resolve_dataset_binding(db, payload.dataset_id)
    formula = await generate_metric_formula(
        datasource_context={
            "name": datasource.name,
            "metadata_prompt": datasource.metadata_prompt,
            "schema_metadata": datasource.schema_metadata,
        },
        name=payload.name,
        definition=payload.definition,
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
    assert_metric_can_delete(db, metric)
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


@router.post("/{metric_id}/compute")
def compute_metric(
    metric_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Execute the metric SQL and update last_value / last_computed_at."""
    from datetime import datetime
    from sqlalchemy import text
    from app.db.session import get_datasource_engine

    metric = db.query(Metric).filter(Metric.id == metric_id).first()
    if not metric:
        raise HTTPException(status_code=404, detail="指标不存在")

    datasource = db.query(DataSource).filter(DataSource.id == metric.datasource_id).first() if metric.datasource_id else None
    if not datasource:
        raise HTTPException(status_code=400, detail="指标未绑定数据源")

    # Derive main table from the linked dataset's fields_json
    dataset = db.query(Dataset).filter(Dataset.id == metric.dataset_id).first() if metric.dataset_id else None
    fields_json = (dataset.fields_json or {}) if dataset else {}
    table = str(fields_json.get("table") or "").strip()

    formula = (metric.formula or "").strip()

    if formula and table:
        sql = f"SELECT {formula} AS _val FROM {table}"
    elif table and metric.column_name:
        agg = (metric.aggregation or "SUM").upper()
        col = metric.column_name.strip()
        sql = f"SELECT {agg}({col}) AS _val FROM {table}"
    else:
        raise HTTPException(status_code=400, detail="指标缺少计算口径：请配置 column_name 或 formula，并确保数据集已设置主表")

    try:
        source_type = getattr(datasource, "source_type", "database")
        if source_type == "excel":
            from app.core.excel_executor import execute_excel_query
            from app.core.excel_uploads import resolve_excel_source_path
            file_path = resolve_excel_source_path(datasource.database_url)
            result = execute_excel_query(file_path, f"SELECT {formula or metric.column_name} AS _val FROM {table}")
            rows = result.get("rows", [])
            val = float(rows[0][0]) if rows and rows[0][0] is not None else None
        else:
            engine = get_datasource_engine(datasource.database_url)
            with engine.connect() as conn:
                row = conn.execute(text(sql)).fetchone()
            val = float(row[0]) if row and row[0] is not None else None
    except Exception as exc:
        metric.quality_status = "error"
        db.commit()
        raise HTTPException(status_code=500, detail=f"SQL执行失败: {exc}")

    now = datetime.utcnow()
    metric.last_value = val
    metric.last_computed_at = now
    metric.quality_status = "normal"
    metric.data_updated_at = now
    db.commit()
    db.refresh(metric)

    return {"last_value": val, "computed_at": now.isoformat()}
