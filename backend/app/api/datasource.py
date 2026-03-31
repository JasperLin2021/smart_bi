import json
import shutil
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
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
    SchemaMetadata,
    TableSchema,
)
from app.core.excel_executor import test_excel_connection, generate_excel_metadata
from app.core.excel_uploads import build_excel_storage_path, is_allowed_excel_filename
from app.core.schema_detector import detect_schema, schema_to_prompt
from app.core.drill_config import generate_drill_config
from app.core.schema_enrichment import generate_column_descriptions

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
        schema_metadata=json.dumps(payload.schema_metadata.model_dump(), ensure_ascii=False)
        if payload.schema_metadata
        else None,
        drill_config=json.dumps(payload.drill_config.model_dump(), ensure_ascii=False)
        if payload.drill_config
        else None,
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


@router.post("/upload-excel")
def upload_excel_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    del current_user

    filename = file.filename or ""
    if not is_allowed_excel_filename(filename):
        raise HTTPException(status_code=400, detail="仅支持上传 .xlsx 或 .xls 文件")

    storage_path = build_excel_storage_path(filename)
    try:
        with storage_path.open("wb") as output:
            shutil.copyfileobj(file.file, output)
    finally:
        file.file.close()

    return {
        "status": "ok",
        "filename": filename,
        "database_url": str(storage_path),
    }


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

    for field in ["name", "slug", "database_url", "source_type", "metadata_prompt", "metrics_prompt", "text2sql_prompt", "is_active", "org_id"]:
        val = getattr(payload, field, None)
        if val is not None:
            setattr(ds, field, val)
    if payload.recommend_questions is not None:
        ds.recommend_questions = json.dumps(payload.recommend_questions, ensure_ascii=False)
    if payload.schema_metadata is not None:
        ds.schema_metadata = json.dumps(payload.schema_metadata.model_dump(), ensure_ascii=False)
    if payload.drill_config is not None:
        ds.drill_config = json.dumps(payload.drill_config.model_dump(), ensure_ascii=False)

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
    schema_meta = None
    if ds.schema_metadata:
        try:
            schema_meta = json.loads(ds.schema_metadata)
        except (json.JSONDecodeError, TypeError):
            schema_meta = None
    drill_config = None
    if ds.drill_config:
        try:
            drill_config = json.loads(ds.drill_config)
        except (json.JSONDecodeError, TypeError):
            drill_config = None
    return {
        "id": ds.id,
        "name": ds.name,
        "slug": ds.slug,
        "source_type": ds.source_type or "database",
        "metadata_prompt": ds.metadata_prompt,
        "schema_metadata": schema_meta,
        "drill_config": drill_config,
        "metrics_prompt": ds.metrics_prompt,
        "text2sql_prompt": ds.text2sql_prompt,
        "recommend_questions": recommend,
        "is_active": ds.is_active,
        "org_id": ds.org_id,
    }


@router.post("/{datasource_id}/detect-schema")
def detect_datasource_schema(
    datasource_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Auto-detect schema from Excel file or database."""
    ds = db.query(DataSource).filter(DataSource.id == datasource_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    if not check_datasource_access(current_user, ds):
        raise HTTPException(status_code=403, detail="无权访问此数据源")
    
    try:
        schema = detect_schema(ds.database_url, ds.source_type)
        return schema
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"检测schema失败: {e}")


@router.post("/{datasource_id}/generate-prompt")
def generate_prompt_from_schema(
    datasource_id: int,
    schema: SchemaMetadata,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate metadata_prompt text from schema metadata."""
    ds = db.query(DataSource).filter(DataSource.id == datasource_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    if not check_datasource_access(current_user, ds):
        raise HTTPException(status_code=403, detail="无权访问此数据源")
    
    prompt = schema_to_prompt(schema)
    return {"metadata_prompt": prompt}


@router.post("/{datasource_id}/generate-column-descriptions")
async def generate_column_descriptions_for_table(
    datasource_id: int,
    table: TableSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ds = db.query(DataSource).filter(DataSource.id == datasource_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    if not check_datasource_access(current_user, ds):
        raise HTTPException(status_code=403, detail="无权访问此数据源")

    try:
        enriched_table, filled_count = await generate_column_descriptions(ds.name, table)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"生成字段说明失败: {exc}")

    return {"table": enriched_table.model_dump(), "filled_count": filled_count}


@router.post("/{datasource_id}/generate-drill-config")
def generate_drill_config_from_schema(
    datasource_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ds = db.query(DataSource).filter(DataSource.id == datasource_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    if not check_datasource_access(current_user, ds):
        raise HTTPException(status_code=403, detail="无权访问此数据源")

    if ds.schema_metadata:
        try:
            schema = SchemaMetadata.model_validate(json.loads(ds.schema_metadata))
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=f"现有表结构无效: {exc}")
    else:
        try:
            schema = detect_schema(ds.database_url, ds.source_type)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"自动生成钻取规则失败: {exc}")

    config = generate_drill_config(schema)
    return config
