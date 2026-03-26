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
from app.core.excel_executor import test_excel_connection, generate_excel_metadata

router = APIRouter(prefix="/datasources", tags=["datasources"])


def check_datasource_access(user: User, ds: DataSource):
    """Check if user can access this datasource"""
    if user.role == "super_admin":
        return True
    return ds.org_id == user.org_id


@router.get("", response_model=List[DataSourceListItem])
def list_datasources(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(DataSource).filter(DataSource.is_active == 1)
    if current_user.role != "super_admin":
        query = query.filter(DataSource.org_id == current_user.org_id)
    return query.all()


@router.post("", response_model=DataSourceOut)
def create_datasource(
    payload: DataSourceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = db.query(DataSource).filter(
        (DataSource.slug == payload.slug) | (DataSource.name == payload.name)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="数据源名称或标识已存在")

    # Auto-generate metadata for Excel sources if not provided
    metadata_prompt = payload.metadata_prompt
    if payload.source_type == "excel" and not metadata_prompt:
        try:
            metadata_prompt = generate_excel_metadata(payload.database_url)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"无法读取Excel文件: {e}")

    # Determine org_id
    org_id = None
    if current_user.role != "super_admin":
        org_id = current_user.org_id
    elif payload.org_id:
        org_id = payload.org_id

    ds = DataSource(
        name=payload.name,
        slug=payload.slug,
        database_url=payload.database_url,
        source_type=payload.source_type or "database",
        metadata_prompt=metadata_prompt,
        metrics_prompt=payload.metrics_prompt,
        text2sql_prompt=payload.text2sql_prompt,
        recommend_questions=json.dumps(payload.recommend_questions, ensure_ascii=False)
        if payload.recommend_questions
        else None,
        org_id=org_id,
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
    if not check_datasource_access(current_user, ds):
        raise HTTPException(status_code=403, detail="无权访问此数据源")
    return _to_out(ds)


@router.put("/{datasource_id}", response_model=DataSourceOut)
def update_datasource(
    datasource_id: int,
    payload: DataSourceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ds = db.query(DataSource).filter(DataSource.id == datasource_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    if not check_datasource_access(current_user, ds):
        raise HTTPException(status_code=403, detail="无权修改此数据源")

    for field in ["name", "slug", "database_url", "source_type", "metadata_prompt", "metrics_prompt", "text2sql_prompt", "is_active"]:
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
    ds = db.query(DataSource).filter(DataSource.id == datasource_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    if not check_datasource_access(current_user, ds):
        raise HTTPException(status_code=403, detail="无权删除此数据源")
    db.delete(ds)
    db.commit()
    return {"status": "ok"}


@router.post("/{datasource_id}/test")
def test_datasource(
    datasource_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ds = db.query(DataSource).filter(DataSource.id == datasource_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    if not check_datasource_access(current_user, ds):
        raise HTTPException(status_code=403, detail="无权访问此数据源")
    
    # Handle Excel sources differently
    if ds.source_type == "excel":
        return test_excel_connection(ds.database_url)
    
    # Database sources use SQLAlchemy
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
        "source_type": ds.source_type or "database",
        "metadata_prompt": ds.metadata_prompt,
        "metrics_prompt": ds.metrics_prompt,
        "text2sql_prompt": ds.text2sql_prompt,
        "recommend_questions": recommend,
        "is_active": ds.is_active,
    }
