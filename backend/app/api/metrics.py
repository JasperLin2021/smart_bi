from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.auth import get_current_user
from app.db.session import get_db
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
    _get_datasource_or_404(db, payload.datasource_id)
    existing = db.query(Metric).filter(Metric.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="指标名称已存在")
    metric = Metric(**payload.model_dump())
    db.add(metric)
    db.commit()
    sync_datasource_metrics_prompt(db, payload.datasource_id)
    db.commit()
    db.refresh(metric)
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
    if payload.datasource_id is not None:
        _get_datasource_or_404(db, payload.datasource_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(metric, key, value)
    db.commit()
    if previous_datasource_id:
        sync_datasource_metrics_prompt(db, previous_datasource_id)
    if metric.datasource_id and metric.datasource_id != previous_datasource_id:
        sync_datasource_metrics_prompt(db, metric.datasource_id)
    elif metric.datasource_id:
        sync_datasource_metrics_prompt(db, metric.datasource_id)
    db.commit()
    db.refresh(metric)
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
    db.delete(metric)
    db.commit()
    if datasource_id:
        sync_datasource_metrics_prompt(db, datasource_id)
        db.commit()
    return {"status": "ok"}
