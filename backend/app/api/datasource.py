import json
import re
import shutil
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from sqlalchemy import inspect, text, create_engine
from typing import List

from app.api.auth import get_current_user
from app.db.session import get_db, get_datasource_engine
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
from app.core.excel_executor import (
    execute_excel_query,
    generate_excel_metadata,
    get_excel_tables,
    test_excel_connection,
)
from app.core.excel_uploads import build_excel_storage_path, is_allowed_excel_filename
from app.core.schema_detector import detect_schema, schema_to_prompt
from app.core.drill_config import generate_drill_config
from app.core.recommend_questions import generate_recommend_questions
from app.core.schema_enrichment import generate_column_descriptions
from app.core.audit import try_record_audit_log
from app.core.safe_delete import assert_datasource_can_delete

router = APIRouter(prefix="/datasources", tags=["datasources"])
SAFE_EXCEL_TABLE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def check_datasource_access(user: User, ds: DataSource):
    """Check if user can access this datasource"""
    if user.role == "super_admin":
        return True
    return ds.org_id == user.org_id


def _clamp_preview_limit(limit: int) -> int:
    return max(1, min(limit, 500))


def _quote_table_name(engine, table: str) -> str:
    preparer = engine.dialect.identifier_preparer
    return ".".join(preparer.quote(part) for part in table.split("."))


def _database_table_exists(engine, table: str) -> bool:
    inspector = inspect(engine)
    if "." in table:
        schema, table_name = table.rsplit(".", 1)
        return table_name in inspector.get_table_names(schema=schema)
    return table in inspector.get_table_names()


def _fetch_database_preview(database_url: str, table: str, limit: int) -> dict:
    engine = get_datasource_engine(database_url)
    if not _database_table_exists(engine, table):
        raise HTTPException(status_code=404, detail="数据表不存在")

    quoted_table = _quote_table_name(engine, table)
    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT * FROM {quoted_table} LIMIT {limit}"))
        columns = list(result.keys())
        rows = [dict(row._mapping) for row in result.fetchall()]
    return {"columns": columns, "rows": rows}


def _fetch_excel_preview(file_path: str, table: str, limit: int) -> dict:
    tables = get_excel_tables(file_path)
    if table not in tables:
        raise HTTPException(status_code=404, detail="数据表不存在")
    if not SAFE_EXCEL_TABLE_RE.match(table):
        raise HTTPException(status_code=400, detail="数据表名称不合法")
    return execute_excel_query(file_path, f"SELECT * FROM {table} LIMIT {limit}")


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

    source_type = payload.source_type or "database"
    metadata_prompt = payload.metadata_prompt or ""
    schema_metadata = payload.schema_metadata
    if schema_metadata is None:
        try:
            schema_metadata = detect_schema(payload.database_url, source_type)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"自动检测表结构失败: {e}")
    if not metadata_prompt:
        if source_type == "excel":
            try:
                metadata_prompt = generate_excel_metadata(payload.database_url)
            except Exception:
                metadata_prompt = schema_to_prompt(schema_metadata)
        else:
            metadata_prompt = schema_to_prompt(schema_metadata)

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
        source_type=source_type,
        metadata_prompt=metadata_prompt,
        schema_metadata=json.dumps(schema_metadata.model_dump(), ensure_ascii=False)
        if schema_metadata
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
    try_record_audit_log(
        db,
        actor=current_user,
        action="datasource.create",
        resource_type="datasource",
        resource_id=ds.id,
        resource_name=ds.name,
        org_id=ds.org_id,
        message="数据源已创建",
        detail={
            "slug": ds.slug,
            "source_type": ds.source_type,
            "schema_detected": schema_metadata is not None,
            "table_count": len(schema_metadata.tables) if schema_metadata else 0,
        },
    )
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
    try_record_audit_log(
        db,
        actor=current_user,
        action="datasource.update",
        resource_type="datasource",
        resource_id=ds.id,
        resource_name=ds.name,
        org_id=ds.org_id,
        message="数据源已更新",
        detail={"fields": list(payload.model_dump(exclude_unset=True).keys())},
    )
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
    assert_datasource_can_delete(db, ds)
    ds_id = ds.id
    ds_name = ds.name
    ds_org_id = ds.org_id
    db.delete(ds)
    db.commit()
    try_record_audit_log(
        db,
        actor=current_user,
        action="datasource.delete",
        resource_type="datasource",
        resource_id=ds_id,
        resource_name=ds_name,
        org_id=ds_org_id,
        message="数据源已删除",
    )
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
        result = test_excel_connection(ds.database_url)
        try_record_audit_log(
            db,
            actor=current_user,
            action="datasource.test",
            resource_type="datasource",
            resource_id=ds.id,
            resource_name=ds.name,
            org_id=ds.org_id,
            status="success" if result.get("status") == "ok" else "error",
            message=result.get("message"),
        )
        return result
    
    # Database sources use SQLAlchemy
    try:
        test_engine = create_engine(ds.database_url, pool_pre_ping=True)
        with test_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        test_engine.dispose()
        try_record_audit_log(
            db,
            actor=current_user,
            action="datasource.test",
            resource_type="datasource",
            resource_id=ds.id,
            resource_name=ds.name,
            org_id=ds.org_id,
            message="连接成功",
        )
        return {"status": "ok", "message": "连接成功"}
    except Exception as exc:
        try_record_audit_log(
            db,
            actor=current_user,
            action="datasource.test",
            resource_type="datasource",
            resource_id=ds.id,
            resource_name=ds.name,
            org_id=ds.org_id,
            status="error",
            message=f"连接失败: {exc}",
        )
        return {"status": "error", "message": f"连接失败: {exc}"}


@router.get("/{datasource_id}/preview")
def preview_datasource_table(
    datasource_id: int,
    table: str,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ds = db.query(DataSource).filter(DataSource.id == datasource_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    if not check_datasource_access(current_user, ds):
        raise HTTPException(status_code=403, detail="无权访问此数据源")

    safe_limit = _clamp_preview_limit(limit)
    try:
        if ds.source_type == "excel":
            preview = _fetch_excel_preview(ds.database_url, table, safe_limit)
        else:
            preview = _fetch_database_preview(ds.database_url, table, safe_limit)
    except HTTPException:
        raise
    except Exception as exc:
        try_record_audit_log(
            db,
            actor=current_user,
            action="datasource.preview",
            resource_type="datasource",
            resource_id=ds.id,
            resource_name=ds.name,
            org_id=ds.org_id,
            status="error",
            message=f"数据预览失败: {exc}",
            detail={"table": table, "limit": safe_limit},
        )
        raise HTTPException(status_code=400, detail=f"数据预览失败: {exc}")

    try_record_audit_log(
        db,
        actor=current_user,
        action="datasource.preview",
        resource_type="datasource",
        resource_id=ds.id,
        resource_name=ds.name,
        org_id=ds.org_id,
        message="数据预览成功",
        detail={"table": table, "limit": safe_limit, "row_count": len(preview.get("rows", []))},
    )
    return jsonable_encoder(preview)


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
        try_record_audit_log(
            db,
            actor=current_user,
            action="datasource.detect_schema",
            resource_type="datasource",
            resource_id=ds.id,
            resource_name=ds.name,
            org_id=ds.org_id,
            message="表结构检测成功",
            detail={"table_count": len(schema.tables)},
        )
        return schema
    except Exception as e:
        try_record_audit_log(
            db,
            actor=current_user,
            action="datasource.detect_schema",
            resource_type="datasource",
            resource_id=ds.id,
            resource_name=ds.name,
            org_id=ds.org_id,
            status="error",
            message=f"检测schema失败: {e}",
        )
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
    try_record_audit_log(
        db,
        actor=current_user,
        action="datasource.generate_prompt",
        resource_type="datasource",
        resource_id=ds.id,
        resource_name=ds.name,
        org_id=ds.org_id,
        message="元数据提示词已生成",
        detail={"table_count": len(schema.tables)},
    )
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
        try_record_audit_log(
            db,
            actor=current_user,
            action="datasource.generate_column_descriptions",
            resource_type="datasource",
            resource_id=ds.id,
            resource_name=ds.name,
            org_id=ds.org_id,
            status="error",
            message=f"生成字段说明失败: {exc}",
        )
        raise HTTPException(status_code=502, detail=f"生成字段说明失败: {exc}")

    try_record_audit_log(
        db,
        actor=current_user,
        action="datasource.generate_column_descriptions",
        resource_type="datasource",
        resource_id=ds.id,
        resource_name=ds.name,
        org_id=ds.org_id,
        message="字段说明已生成",
        detail={"table": table.name, "filled_count": filled_count},
    )
    return {"table": enriched_table.model_dump(), "filled_count": filled_count}


@router.post("/{datasource_id}/generate-recommend-questions")
async def generate_recommend_questions_for_datasource(
    datasource_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ds = db.query(DataSource).filter(DataSource.id == datasource_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    if not check_datasource_access(current_user, ds):
        raise HTTPException(status_code=403, detail="无权访问此数据源")

    schema = None
    if ds.schema_metadata:
        try:
            schema = SchemaMetadata.model_validate(json.loads(ds.schema_metadata))
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=f"现有表结构无效: {exc}")

    try:
        questions = await generate_recommend_questions(
            datasource_name=ds.name,
            source_type=ds.source_type or "database",
            metadata_prompt=ds.metadata_prompt or "",
            metrics_prompt=ds.metrics_prompt,
            schema=schema,
        )
    except Exception as exc:
        try_record_audit_log(
            db,
            actor=current_user,
            action="datasource.generate_recommend_questions",
            resource_type="datasource",
            resource_id=ds.id,
            resource_name=ds.name,
            org_id=ds.org_id,
            status="error",
            message=f"生成推荐问题失败: {exc}",
        )
        raise HTTPException(status_code=502, detail=f"生成推荐问题失败: {exc}")

    try_record_audit_log(
        db,
        actor=current_user,
        action="datasource.generate_recommend_questions",
        resource_type="datasource",
        resource_id=ds.id,
        resource_name=ds.name,
        org_id=ds.org_id,
        message="推荐问题已生成",
        detail={"question_count": len(questions), "has_schema": schema is not None},
    )
    return {"recommend_questions": questions}


@router.get("/{datasource_id}/schema-simple")
def get_schema_simple(
    datasource_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return {tables: [{name, columns: [str]}]} for SQL autocomplete."""
    ds = db.query(DataSource).filter(DataSource.id == datasource_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    if not check_datasource_access(current_user, ds):
        raise HTTPException(status_code=403, detail="无权访问此数据源")

    # Prefer cached schema_metadata to avoid a live DB round-trip
    if ds.schema_metadata:
        try:
            schema = SchemaMetadata.model_validate(json.loads(ds.schema_metadata))
            return {
                "tables": [
                    {"name": t.name, "columns": [c.name for c in t.columns]}
                    for t in schema.tables
                ]
            }
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    # Fallback: live detect
    try:
        schema = detect_schema(ds.database_url, ds.source_type)
        return {
            "tables": [
                {"name": t.name, "columns": [c.name for c in t.columns]}
                for t in schema.tables
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"获取表结构失败: {e}")


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
    try_record_audit_log(
        db,
        actor=current_user,
        action="datasource.generate_drill_config",
        resource_type="datasource",
        resource_id=ds.id,
        resource_name=ds.name,
        org_id=ds.org_id,
        message="候选钻取规则已生成",
        detail={
            "dimensions": len(config.get("dimensions", [])),
            "metrics": len(config.get("metrics", [])),
            "paths": len(config.get("paths", [])),
        },
    )
    return config
