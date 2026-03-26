import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text, create_engine
from typing import List

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.datasource import DataSource
from app.models.user import User
from app.schemas.datasource import (
    DataSourceCreate,
    DataSourceUpdate,
    DataSourceOut,
    DataSourceListItem,
)

router = APIRouter(prefix="/datasources", tags=["datasources"])


def ensure_admin(user: User):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="无权限")


@router.get("", response_model=List[DataSourceListItem])
def list_datasources(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = db.query(DataSource).filter(DataSource.is_active == 1).all()
    return items


@router.post("", response_model=DataSourceOut)
def create_datasource(
    payload: DataSourceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_admin(current_user)
    existing = db.query(DataSource).filter(
        (DataSource.slug == payload.slug) | (DataSource.name == payload.name)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="数据源名称或标识已存在")

    ds = DataSource(
        name=payload.name,
        slug=payload.slug,
        database_url=payload.database_url,
        metadata_prompt=payload.metadata_prompt,
        metrics_prompt=payload.metrics_prompt,
        text2sql_prompt=payload.text2sql_prompt,
        recommend_questions=json.dumps(payload.recommend_questions, ensure_ascii=False)
        if payload.recommend_questions
        else None,
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)
    return _to_out(ds)


@router.get("/{datasource_id}", response_model=DataSourceOut)
def get_datasource(
    datasource_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ds = db.query(DataSource).filter(DataSource.id == datasource_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    return _to_out(ds)


@router.put("/{datasource_id}", response_model=DataSourceOut)
def update_datasource(
    datasource_id: int,
    payload: DataSourceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_admin(current_user)
    ds = db.query(DataSource).filter(DataSource.id == datasource_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")

    for field in ["name", "slug", "database_url", "metadata_prompt", "metrics_prompt", "text2sql_prompt", "is_active"]:
        val = getattr(payload, field, None)
        if val is not None:
            setattr(ds, field, val)
    if payload.recommend_questions is not None:
        ds.recommend_questions = json.dumps(payload.recommend_questions, ensure_ascii=False)

    db.commit()
    db.refresh(ds)
    return _to_out(ds)


@router.delete("/{datasource_id}")
def delete_datasource(
    datasource_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_admin(current_user)
    ds = db.query(DataSource).filter(DataSource.id == datasource_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    db.delete(ds)
    db.commit()
    return {"status": "ok"}


@router.post("/{datasource_id}/test")
def test_datasource(
    datasource_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_admin(current_user)
    ds = db.query(DataSource).filter(DataSource.id == datasource_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    try:
        test_engine = create_engine(ds.database_url, pool_pre_ping=True)
        with test_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        test_engine.dispose()
        return {"status": "ok", "message": "连接成功"}
    except Exception as exc:
        return {"status": "error", "message": f"连接失败: {exc}"}


def _to_out(ds: DataSource) -> dict:
    recommend = None
    if ds.recommend_questions:
        try:
            recommend = json.loads(ds.recommend_questions)
        except (json.JSONDecodeError, TypeError):
            recommend = None
    return {
        "id": ds.id,
        "name": ds.name,
        "slug": ds.slug,
        "metadata_prompt": ds.metadata_prompt,
        "metrics_prompt": ds.metrics_prompt,
        "text2sql_prompt": ds.text2sql_prompt,
        "recommend_questions": recommend,
        "is_active": ds.is_active,
    }
