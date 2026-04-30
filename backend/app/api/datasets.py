import re
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import inspect, or_, text
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.audit import try_record_audit_log
from app.core.excel_executor import execute_excel_query, get_excel_tables
from app.db.session import get_db
from app.db.session import get_datasource_engine
from app.models.catalog import DataAsset
from app.models.dataset import Dataset, DatasetRefreshLog
from app.models.datasource import DataSource
from app.models.user import User
from app.schemas.dataset import (
    DatasetCreate,
    DatasetListResponse,
    DatasetOut,
    DatasetPreviewRequest,
    DatasetPreviewResponse,
    DatasetRefreshLogListResponse,
    DatasetRefreshLogOut,
    DatasetUpdate,
)

router = APIRouter(prefix="/datasets", tags=["datasets"])

VALID_DATASET_STATUSES = {"draft", "published", "archived"}
VALID_VISIBILITIES = {"private", "org"}
SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
FILTER_RE = re.compile(
    r"^\s*(?P<field>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?)\s*"
    r"(?P<op>IS\s+NOT\s+NULL|IS\s+NULL|>=|<=|!=|=|>|<|LIKE)\s*"
    r"(?P<value>.*?)\s*$",
    re.IGNORECASE,
)
JOIN_RE = re.compile(
    r"^\s*(?P<type>LEFT\s+JOIN|INNER\s+JOIN|RIGHT\s+JOIN|FULL\s+JOIN)\s+"
    r"(?P<left>[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*)\s*"
    r"(?P<op>=|!=)\s*"
    r"(?P<right>[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*)\s*$",
    re.IGNORECASE,
)
AGGREGATION_RE = re.compile(
    r"^\s*(?P<fn>SUM|AVG|COUNT|MIN|MAX)\s*\(\s*"
    r"(?P<field>\*|[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?)\s*\)\s*$",
    re.IGNORECASE,
)


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


def _get_dataset_for_user(db: Session, dataset_id: int, user: User) -> Dataset:
    dataset = _apply_visibility(db.query(Dataset), user).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")
    return dataset


def _clamp_preview_limit(limit: int) -> int:
    return max(1, min(limit, 5000))


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _source_table(dataset: Dataset) -> str:
    fields_json = dataset.fields_json if isinstance(dataset.fields_json, dict) else {}
    table = str(fields_json.get("table") or "").strip()
    if not table:
        fields = _as_list(fields_json.get("fields"))
        for field in fields:
            text_value = str(field)
            if "." in text_value:
                return text_value.split(".", 1)[0]
    if not table:
        raise HTTPException(status_code=400, detail="数据集缺少主表配置")
    return table


def _assert_safe_identifier(identifier: str, label: str) -> str:
    if not SAFE_IDENTIFIER_RE.match(identifier):
        raise HTTPException(status_code=400, detail=f"{label}不合法")
    return identifier


def _split_field(field: str, default_table: str) -> tuple[str, str]:
    clean = str(field).strip()
    if "." in clean:
        table, column = clean.split(".", 1)
    else:
        table, column = default_table, clean
    return (
        _assert_safe_identifier(table, "表名"),
        _assert_safe_identifier(column, "字段名"),
    )


def _quote_table(engine, table: str) -> str:
    preparer = engine.dialect.identifier_preparer
    return ".".join(preparer.quote(part) for part in table.split("."))


def _quote_column_ref(engine, field: str, default_table: str) -> str:
    table, column = _split_field(field, default_table)
    preparer = engine.dialect.identifier_preparer
    return f"{preparer.quote(table)}.{preparer.quote(column)}"


def _field_alias(field: str, default_table: str) -> str:
    _, column = _split_field(field, default_table)
    return column


def _validate_database_table_and_columns(engine, table: str, fields: list[str]) -> None:
    inspector = inspect(engine)
    if table not in inspector.get_table_names():
        raise HTTPException(status_code=404, detail="数据表不存在")
    table_columns = {column["name"] for column in inspector.get_columns(table)}
    for field in fields:
        field_table, field_column = _split_field(field, table)
        if field_table != table:
            continue
        if field_column not in table_columns:
            raise HTTPException(status_code=400, detail=f"字段不存在: {field}")


def _selected_fields(dataset: Dataset, table: str) -> list[str]:
    fields_json = dataset.fields_json if isinstance(dataset.fields_json, dict) else {}
    fields = [str(field) for field in _as_list(fields_json.get("fields")) if str(field).strip()]
    return fields or [f"{table}.*"]


def _derived_expressions(dataset: Dataset) -> list[str]:
    derived_json = dataset.derived_columns_json if isinstance(dataset.derived_columns_json, dict) else {}
    return [str(item) for item in _as_list(derived_json.get("expressions")) if str(item).strip()]


def _join_expressions(dataset: Dataset) -> list[str]:
    joins_json = dataset.joins_json if isinstance(dataset.joins_json, dict) else {}
    return [str(item) for item in _as_list(joins_json.get("joins")) if str(item).strip()]


def _filter_expressions(dataset: Dataset) -> list[Any]:
    filters_json = dataset.filters_json if isinstance(dataset.filters_json, dict) else {}
    return _as_list(filters_json.get("filters"))


def _aggregation_expressions(dataset: Dataset) -> list[str]:
    aggregations_json = dataset.aggregations_json if isinstance(dataset.aggregations_json, dict) else {}
    return [str(item) for item in _as_list(aggregations_json.get("aggregations")) if str(item).strip()]


def _render_derived_expression(engine, expression: str, default_table: str) -> str:
    if any(token in expression for token in (";", "--", "/*", "*/")):
        raise HTTPException(status_code=400, detail="派生列表达式不合法")
    if "=" not in expression:
        raise HTTPException(status_code=400, detail="派生列表达式需要使用 name = expression 格式")
    alias, raw_expr = expression.split("=", 1)
    alias = _assert_safe_identifier(alias.strip(), "派生列名称")
    raw_expr = raw_expr.strip()
    if not raw_expr:
        raise HTTPException(status_code=400, detail="派生列表达式不能为空")

    def replace_field(match: re.Match[str]) -> str:
        return _quote_column_ref(engine, match.group(0), default_table)

    rendered = re.sub(
        r"\b[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*\b",
        replace_field,
        raw_expr,
    )
    if not re.fullmatch(r"[A-Za-z0-9_\.\"`\[\]\s\+\-\*/\(\),]+", rendered):
        raise HTTPException(status_code=400, detail="派生列表达式包含不支持的字符")
    return f"{rendered} AS {_quote_table(engine, alias)}"


def _render_aggregation(engine, expression: str, default_table: str) -> str:
    match = AGGREGATION_RE.match(expression)
    if not match:
        raise HTTPException(status_code=400, detail=f"聚合表达式不合法: {expression}")
    fn = match.group("fn").upper()
    field = match.group("field")
    if field == "*":
        return f"{fn}(*) AS {_quote_table(engine, fn.lower())}"
    _, column = _split_field(field, default_table)
    alias = f"{fn.lower()}_{column}"
    return f"{fn}({_quote_column_ref(engine, field, default_table)}) AS {_quote_table(engine, alias)}"


def _normalize_filter_value(value: str) -> str:
    clean = value.strip()
    if len(clean) >= 2 and clean[0] == clean[-1] and clean[0] in {"'", '"'}:
        return clean[1:-1]
    return clean


def _render_filter(engine, item: Any, default_table: str, params: dict[str, Any], index: int) -> str:
    if isinstance(item, dict):
        field = str(item.get("field") or item.get("column") or "").strip()
        operator = str(item.get("operator") or item.get("op") or "=").strip().upper()
        value = item.get("value")
    else:
        match = FILTER_RE.match(str(item))
        if not match:
            raise HTTPException(status_code=400, detail=f"筛选条件不合法: {item}")
        field = match.group("field")
        operator = re.sub(r"\s+", " ", match.group("op").upper())
        value = _normalize_filter_value(match.group("value"))

    if operator not in {"=", "!=", ">", ">=", "<", "<=", "LIKE", "IS NULL", "IS NOT NULL"}:
        raise HTTPException(status_code=400, detail=f"筛选操作符不支持: {operator}")
    column_ref = _quote_column_ref(engine, field, default_table)
    if operator in {"IS NULL", "IS NOT NULL"}:
        return f"{column_ref} {operator}"
    param_name = f"filter_{index}"
    if operator == "LIKE":
        text_value = str(value)
        params[param_name] = text_value if "%" in text_value else f"%{text_value}%"
    else:
        params[param_name] = value
    return f"{column_ref} {operator} :{param_name}"


def _render_joins(engine, joins: list[str], default_table: str) -> list[str]:
    rendered: list[str] = []
    for item in joins:
        match = JOIN_RE.match(item)
        if not match:
            raise HTTPException(status_code=400, detail=f"Join 关系不合法: {item}")
        join_type = re.sub(r"\s+", " ", match.group("type").upper())
        left_table, _ = _split_field(match.group("left"), default_table)
        right_table, _ = _split_field(match.group("right"), default_table)
        if left_table == default_table and right_table != default_table:
            join_table = right_table
        elif right_table == default_table and left_table != default_table:
            join_table = left_table
        else:
            join_table = right_table
        condition = (
            f"{_quote_column_ref(engine, match.group('left'), default_table)} "
            f"{match.group('op')} "
            f"{_quote_column_ref(engine, match.group('right'), default_table)}"
        )
        rendered.append(f"{join_type} {_quote_table(engine, join_table)} ON {condition}")
    return rendered


def _build_dataset_sql(dataset: Dataset, datasource: DataSource, limit: int) -> tuple[str, dict[str, Any]]:
    table = _source_table(dataset)
    fields = _selected_fields(dataset, table)
    aggregations = _aggregation_expressions(dataset)
    params: dict[str, Any] = {"limit": _clamp_preview_limit(limit)}
    engine = get_datasource_engine(datasource.database_url)

    if datasource.source_type != "excel":
        validation_fields = [field for field in fields if not field.endswith(".*")]
        for expression in _derived_expressions(dataset):
            validation_fields.extend(
                re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*\b", expression)
            )
        _validate_database_table_and_columns(engine, table, validation_fields)
    elif table not in get_excel_tables(datasource.database_url):
        raise HTTPException(status_code=404, detail="数据表不存在")

    select_parts: list[str] = []
    group_by_parts: list[str] = []
    for field in fields:
        if field.endswith(".*"):
            select_parts.append("*")
            continue
        alias = _field_alias(field, table)
        column_ref = _quote_column_ref(engine, field, table)
        select_parts.append(f"{column_ref} AS {_quote_table(engine, alias)}")
        if aggregations:
            group_by_parts.append(column_ref)

    for expression in _derived_expressions(dataset):
        select_parts.append(_render_derived_expression(engine, expression, table))

    for expression in aggregations:
        select_parts.append(_render_aggregation(engine, expression, table))

    if not select_parts:
        select_parts.append("*")

    join_parts = _render_joins(engine, _join_expressions(dataset), table)
    where_parts = [
        _render_filter(engine, item, table, params, index)
        for index, item in enumerate(_filter_expressions(dataset))
    ]
    sql_parts = [
        f"SELECT {', '.join(select_parts)}",
        f"FROM {_quote_table(engine, table)}",
        *join_parts,
    ]
    if where_parts:
        sql_parts.append(f"WHERE {' AND '.join(where_parts)}")
    if group_by_parts:
        sql_parts.append(f"GROUP BY {', '.join(group_by_parts)}")
    sql_parts.append("LIMIT :limit")
    return "\n".join(sql_parts), params


def _execute_dataset_preview(dataset: Dataset, datasource: DataSource, limit: int) -> dict[str, Any]:
    sql, params = _build_dataset_sql(dataset, datasource, limit)
    if datasource.source_type == "excel":
        rendered_sql = sql
        for key, value in params.items():
            if isinstance(value, int):
                rendered_sql = rendered_sql.replace(f":{key}", str(value))
            else:
                rendered_sql = rendered_sql.replace(f":{key}", f"'{str(value).replace("'", "''")}'")
        return execute_excel_query(datasource.database_url, rendered_sql)

    engine = get_datasource_engine(datasource.database_url)
    with engine.connect() as conn:
        result = conn.execute(text(sql), params)
        columns = list(result.keys())
        rows = [dict(row._mapping) for row in result.fetchall()]
    return {"columns": columns, "rows": rows}


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
    return _get_dataset_for_user(db, dataset_id, current_user)


@router.post("/{dataset_id}/preview", response_model=DatasetPreviewResponse)
def preview_dataset(
    dataset_id: int,
    payload: DatasetPreviewRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = _get_dataset_for_user(db, dataset_id, current_user)
    datasource = _get_datasource_for_user(db, dataset.datasource_id, current_user)
    limit = payload.limit if payload else 100
    try:
        preview = _execute_dataset_preview(dataset, datasource, limit)
    except HTTPException:
        raise
    except Exception as exc:
        try_record_audit_log(
            db,
            actor=current_user,
            action="dataset.preview",
            resource_type="dataset",
            resource_id=dataset.id,
            resource_name=dataset.name,
            org_id=dataset.org_id,
            status="error",
            message=f"数据集预览失败: {exc}",
        )
        raise HTTPException(status_code=400, detail=f"数据集预览失败: {exc}")

    response = {
        "dataset_id": dataset.id,
        "columns": preview.get("columns", []),
        "rows": preview.get("rows", []),
        "row_count": len(preview.get("rows", [])),
    }
    try_record_audit_log(
        db,
        actor=current_user,
        action="dataset.preview",
        resource_type="dataset",
        resource_id=dataset.id,
        resource_name=dataset.name,
        org_id=dataset.org_id,
        message="数据集预览成功",
        detail={"limit": _clamp_preview_limit(limit), "row_count": response["row_count"]},
    )
    return jsonable_encoder(response)


@router.post("/{dataset_id}/refresh", response_model=DatasetRefreshLogOut)
def refresh_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")
    if not _can_manage_dataset(current_user, dataset):
        raise HTTPException(status_code=403, detail="无权限")
    datasource = _get_datasource_for_user(db, dataset.datasource_id, current_user)

    status = "success"
    row_count = 0
    message = "刷新成功"
    try:
        preview = _execute_dataset_preview(dataset, datasource, 5000)
        row_count = len(preview.get("rows", []))
    except Exception as exc:
        status = "error"
        message = f"刷新失败: {exc}"

    now = datetime.utcnow()
    dataset.last_refresh_status = status
    dataset.last_refresh_at = now
    dataset.last_refresh_row_count = row_count
    log = DatasetRefreshLog(
        dataset_id=dataset.id,
        status=status,
        row_count=row_count,
        message=message,
        org_id=dataset.org_id,
        triggered_by_id=current_user.id,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    try_record_audit_log(
        db,
        actor=current_user,
        action="dataset.refresh",
        resource_type="dataset",
        resource_id=dataset.id,
        resource_name=dataset.name,
        org_id=dataset.org_id,
        status=status,
        message=message,
        detail={"row_count": row_count},
    )
    if status == "error":
        raise HTTPException(status_code=400, detail=message)
    return log


@router.get("/{dataset_id}/refresh-logs", response_model=DatasetRefreshLogListResponse)
def list_dataset_refresh_logs(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = _get_dataset_for_user(db, dataset_id, current_user)
    query = db.query(DatasetRefreshLog).filter(DatasetRefreshLog.dataset_id == dataset.id)
    return {"items": query.order_by(DatasetRefreshLog.id.desc()).all()}


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
