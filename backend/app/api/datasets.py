import re
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import inspect, or_, text
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.audit import try_record_audit_log
from app.core.config import settings
from app.core.excel_executor import execute_excel_query, get_excel_tables
from app.core.olap import execute_materialized_dataset_preview, write_dataset_to_olap
from app.core.safe_delete import assert_dataset_can_delete, delete_catalog_asset
from app.core.dataset_ai_config import suggest_dataset_ai_config as build_dataset_ai_config
from app.core.drill_config import normalize_drill_config
from app.core.semantic_layer import infer_semantic_model, normalize_semantic_model
from app.db.session import get_db
from app.db.session import get_datasource_engine
from app.models.catalog import AssetLineage, DataAsset
from app.models.dataset import Dataset, DatasetRefreshLog
from app.models.datasource import DataSource
from app.models.user import User
from app.schemas.dataset import (
    DatasetCreate,
    DatasetAIConfigSuggestRequest,
    DatasetAIConfigSuggestResponse,
    DatasetDraftPreviewRequest,
    DatasetListResponse,
    DatasetMaterializeRequest,
    DatasetOut,
    DatasetPreviewRequest,
    DatasetPreviewResponse,
    DatasetRefreshLogListResponse,
    DatasetRefreshLogOut,
    DatasetSemanticModelResponse,
    DatasetSemanticModelUpdate,
    DatasetSemanticModelValidationResponse,
    DatasetUpdate,
)

router = APIRouter(prefix="/datasets", tags=["datasets"])

DATASET_STATUS_DRAFT = "draft"
DATASET_STATUS_PENDING_REVIEW = "pending_review"
DATASET_STATUS_PUBLISHED = "published"
DATASET_STATUS_ARCHIVED = "archived"
DATASET_VISIBILITY_ORG = "org"
DATASET_VISIBILITY_PRIVATE = "private"
DATASET_APPROVER_ROLES = {"dept_admin", "org_admin", "super_admin"}
VALID_DATASET_STATUSES = {
    DATASET_STATUS_DRAFT,
    DATASET_STATUS_PENDING_REVIEW,
    DATASET_STATUS_PUBLISHED,
    DATASET_STATUS_ARCHIVED,
}
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
    r"^\s*(?P<fn>SUM|AVG|COUNT|COUNT_DISTINCT|MIN|MAX)\s*\(\s*"
    r"(?:(?P<distinct>DISTINCT)\s+)?"
    r"(?P<field>\*|[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?)\s*\)\s*$",
    re.IGNORECASE,
)


class _ExcelIdentifierPreparer:
    def quote(self, identifier: str) -> str:
        return f'"{str(identifier).replace('"', '""')}"'


class _ExcelDialect:
    identifier_preparer = _ExcelIdentifierPreparer()


class _ExcelSqlEngine:
    dialect = _ExcelDialect()


EXCEL_SQL_ENGINE = _ExcelSqlEngine()


def _ensure_values(status: str | None = None, visibility: str | None = None) -> None:
    if status is not None and status not in VALID_DATASET_STATUSES:
        raise HTTPException(status_code=400, detail="无效数据集状态")
    if visibility is not None and visibility not in VALID_VISIBILITIES:
        raise HTTPException(status_code=400, detail="无效可见范围")


def _normalize_model_values(values: dict[str, Any], dataset: Dataset | None = None) -> None:
    if "semantic_model_json" in values and values["semantic_model_json"] is not None:
        try:
            values["semantic_model_json"] = normalize_semantic_model(values["semantic_model_json"], dataset)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    if "drill_config_json" in values and values["drill_config_json"] is not None:
        try:
            values["drill_config_json"] = normalize_drill_config(values["drill_config_json"])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))


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


def _can_approve_dataset(db: Session, user: User, dataset: Dataset) -> bool:
    if user.role == "super_admin":
        return True
    if user.org_id != dataset.org_id:
        return False
    if user.role == "org_admin":
        return True
    if user.role != "dept_admin":
        return False

    owner = db.query(User).filter(User.id == dataset.owner_id).first() if dataset.owner_id else None
    owner_department_id = getattr(owner, "department_id", None)
    approver_department_id = getattr(user, "department_id", None)
    if owner_department_id and approver_department_id:
        return owner_department_id == approver_department_id
    return True


def _requires_org_visibility_approval(user: User, visibility: str | None, status: str | None) -> bool:
    return (
        visibility == DATASET_VISIBILITY_ORG
        and status == DATASET_STATUS_PUBLISHED
        and user.role not in DATASET_APPROVER_ROLES
    )


def _apply_dataset_publication_workflow(values: dict[str, Any], user: User, dataset: Dataset | None = None) -> bool:
    next_visibility = values.get("visibility", dataset.visibility if dataset else DATASET_VISIBILITY_PRIVATE)
    next_status = values.get("status", dataset.status if dataset else DATASET_STATUS_DRAFT)
    if not _requires_org_visibility_approval(user, next_visibility, next_status):
        return False
    values["visibility"] = DATASET_VISIBILITY_ORG
    values["status"] = DATASET_STATUS_PENDING_REVIEW
    return True


def _sync_dataset_publication_state(db: Session, dataset: Dataset) -> None:
    if dataset.status == DATASET_STATUS_PUBLISHED:
        _sync_dataset_asset(db, dataset)
    else:
        delete_catalog_asset(db, "dataset", dataset.id)


def _apply_visibility(query, user: User):
    if user.role == "super_admin":
        return query
    query = query.filter(Dataset.org_id == user.org_id)
    if user.role == "org_admin":
        return query
    if user.role == "dept_admin":
        return query.filter(
            or_(
                Dataset.status.in_([DATASET_STATUS_PUBLISHED, DATASET_STATUS_PENDING_REVIEW]),
                Dataset.owner_id == user.id,
            )
        )
    return query.filter(or_(Dataset.status == DATASET_STATUS_PUBLISHED, Dataset.owner_id == user.id))


def _get_dataset_for_user(db: Session, dataset_id: int, user: User) -> Dataset:
    dataset = _apply_visibility(db.query(Dataset), user).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")
    return dataset


def _clamp_preview_limit(limit: int) -> int:
    return max(1, min(limit, 5000))


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _field_name(field: Any) -> str:
    """Extract field name from either a string or a dict with a 'name' key."""
    if isinstance(field, dict):
        return str(field.get("field") or field.get("name") or field.get("key") or "").strip()
    return str(field).strip()


def _output_alias(value: Any) -> str | None:
    alias = str(value or "").strip()
    if not alias:
        return None
    if len(alias) > 128 or any(token in alias for token in (";", "--", "/*", "*/", "\x00")):
        raise HTTPException(status_code=400, detail="字段别名不合法")
    return alias


def _field_alias_override(field: Any) -> str | None:
    if not isinstance(field, dict):
        return None
    return _output_alias(field.get("alias") or field.get("label") or field.get("display_name"))


def _quote_output_alias(engine, alias: str) -> str:
    preparer = engine.dialect.identifier_preparer
    return preparer.quote(alias)


def _source_table(dataset: Dataset) -> str:
    fields_json = dataset.fields_json if isinstance(dataset.fields_json, dict) else {}
    table = str(fields_json.get("table") or "").strip()
    if not table:
        fields = _as_list(fields_json.get("dimensions")) or _as_list(fields_json.get("fields"))
        for field in fields:
            name = _field_name(field)
            if "." in name:
                return name.split(".", 1)[0]
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


def _normalized_field_ref(field: str, default_table: str) -> str:
    table, column = _split_field(field, default_table)
    return f"{table}.{column}"


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
    return [item["field"] for item in _dimension_specs(dataset, table)]


def _dimension_specs(dataset: Dataset, table: str) -> list[dict[str, Any]]:
    fields_json = dataset.fields_json if isinstance(dataset.fields_json, dict) else {}
    raw_dimensions = _as_list(fields_json.get("dimensions"))
    raw_plain_fields = _as_list(fields_json.get("fields"))
    has_explicit_dimensions = bool(raw_dimensions) and (
        raw_dimensions != raw_plain_fields or any(isinstance(item, dict) for item in raw_dimensions)
    )
    raw_fields = raw_dimensions or raw_plain_fields
    specs = [
        {"field": _field_name(item), "alias": _field_alias_override(item), "explicit_dimension": has_explicit_dimensions}
        for item in raw_fields
        if _field_name(item)
    ]
    return specs or [{"field": f"{table}.*", "alias": None, "explicit_dimension": False}]


def _dataset_dimension_fields(dataset: Dataset) -> list[str]:
    try:
        table = _source_table(dataset)
    except HTTPException:
        return []
    return [field for field in _selected_fields(dataset, table) if not field.endswith(".*")]


def _normalize_fields_json(fields_json: Any) -> Any:
    if not isinstance(fields_json, dict):
        return fields_json
    normalized = dict(fields_json)
    dimensions = _as_list(normalized.get("dimensions"))
    if not dimensions:
        dimensions = _as_list(normalized.get("fields"))
    if dimensions:
        normalized["dimensions"] = dimensions
        normalized["fields"] = [_field_name(item) for item in dimensions if _field_name(item)]
    metrics = _as_list(normalized.get("metrics"))
    if metrics:
        normalized["metrics"] = metrics
    if "dimension_labels" not in normalized and "field_labels" in normalized:
        normalized["dimension_labels"] = normalized.get("field_labels")
    if "field_labels" not in normalized and "dimension_labels" in normalized:
        normalized["field_labels"] = normalized.get("dimension_labels")
    return normalized


def _derived_expressions(dataset: Dataset) -> list[str]:
    derived_json = dataset.derived_columns_json if isinstance(dataset.derived_columns_json, dict) else {}
    return [str(item) for item in _as_list(derived_json.get("expressions")) if str(item).strip()]


def _join_expressions(dataset: Dataset) -> list[str]:
    joins_json = dataset.joins_json if isinstance(dataset.joins_json, dict) else {}
    result = []
    for item in _as_list(joins_json.get("joins")):
        if isinstance(item, dict):
            # {"type": "LEFT JOIN", "left": "a.id", "right": "b.id"} → canonical string form
            join_type = str(item.get("type") or "JOIN").strip()
            left = str(item.get("left") or "").strip()
            right = str(item.get("right") or "").strip()
            op = str(item.get("op") or "=").strip()
            if left and right:
                result.append(f"{join_type} {left} {op} {right}")
        else:
            s = str(item).strip()
            if s:
                result.append(s)
    return result


def _filter_expressions(dataset: Dataset) -> list[Any]:
    filters_json = dataset.filters_json if isinstance(dataset.filters_json, dict) else {}
    return _as_list(filters_json.get("filters"))


def _aggregation_expressions(dataset: Dataset) -> list[str]:
    return [item["expression"] for item in _metric_specs(dataset)]


def _metric_specs(dataset: Dataset) -> list[dict[str, str | None]]:
    aggregations_json = dataset.aggregations_json if isinstance(dataset.aggregations_json, dict) else {}
    fields_json = dataset.fields_json if isinstance(dataset.fields_json, dict) else {}
    raw_items = _as_list(fields_json.get("metrics")) or _as_list(aggregations_json.get("aggregations"))
    specs: list[dict[str, str | None]] = []
    for item in raw_items:
        alias = None
        if isinstance(item, dict):
            alias = _field_alias_override(item)
            expression = str(item.get("expression") or "").strip()
            if not expression:
                field = _field_name(item)
                aggregation = str(item.get("aggregation") or item.get("fn") or "SUM").strip().upper()
                if field and aggregation:
                    expression = f"{aggregation}({field})"
        else:
            expression = str(item).strip()
        if expression:
            specs.append({"expression": expression, "alias": alias})
    return specs


def _aggregation_field_refs(aggregations: list[str], default_table: str) -> set[str]:
    refs: set[str] = set()
    for expression in aggregations:
        match = AGGREGATION_RE.match(expression)
        if not match:
            continue
        field = match.group("field")
        if field == "*":
            continue
        refs.add(_normalized_field_ref(field, default_table))
    return refs


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


def _render_aggregation(engine, expression: str, default_table: str, alias_override: str | None = None) -> str:
    match = AGGREGATION_RE.match(expression)
    if not match:
        raise HTTPException(status_code=400, detail=f"聚合表达式不合法: {expression}")
    fn = match.group("fn").upper()
    is_distinct = fn == "COUNT_DISTINCT" or bool(match.group("distinct"))
    field = match.group("field")
    if field == "*":
        if is_distinct:
            raise HTTPException(status_code=400, detail=f"聚合表达式不合法: {expression}")
        alias = alias_override or fn.lower()
        return f"{fn}(*) AS {_quote_output_alias(engine, alias)}"
    _, column = _split_field(field, default_table)
    if is_distinct:
        alias = alias_override or f"count_distinct_{column}"
        return f"COUNT(DISTINCT {_quote_column_ref(engine, field, default_table)}) AS {_quote_output_alias(engine, alias)}"
    alias = alias_override or f"{fn.lower()}_{column}"
    return f"{fn}({_quote_column_ref(engine, field, default_table)}) AS {_quote_output_alias(engine, alias)}"


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


def _build_excel_dataset_sql(dataset: Dataset, datasource: DataSource, limit: int | None) -> tuple[str, dict[str, Any]]:
    """Build plain SQL for Excel datasources (no dialect-specific quoting needed)."""
    table = _source_table(dataset)
    if table not in get_excel_tables(datasource.database_url):
        raise HTTPException(status_code=404, detail="数据表不存在")

    engine = EXCEL_SQL_ENGINE
    dimension_specs = _dimension_specs(dataset, table)
    fields = [item["field"] for item in dimension_specs]
    metric_specs = _metric_specs(dataset)
    aggregations = [item["expression"] for item in metric_specs]
    aggregation_fields = _aggregation_field_refs(aggregations, table)
    params: dict[str, Any] = {}
    if limit is not None:
        params["limit"] = _clamp_preview_limit(limit)

    select_parts: list[str] = []
    group_by_parts: list[str] = []
    for spec in dimension_specs:
        field = str(spec["field"])
        if field.endswith(".*"):
            if aggregations:
                continue
            select_parts.append("*")
            continue
        if aggregations and _normalized_field_ref(field, table) in aggregation_fields and not spec.get("explicit_dimension"):
            continue
        alias = spec["alias"] or _field_alias(field, table)
        column_ref = _quote_column_ref(engine, field, table)
        select_parts.append(f"{column_ref} AS {_quote_output_alias(engine, alias)}")
        if aggregations:
            group_by_parts.append(column_ref)

    for expression in _derived_expressions(dataset):
        select_parts.append(_render_derived_expression(engine, expression, table))

    for spec in metric_specs:
        select_parts.append(_render_aggregation(engine, str(spec["expression"]), table, spec["alias"]))

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
    if limit is not None:
        sql_parts.append("LIMIT :limit")
    return "\n".join(sql_parts), params


def _build_dataset_sql(dataset: Dataset, datasource: DataSource, limit: int | None) -> tuple[str, dict[str, Any]]:
    if datasource.source_type == "excel":
        return _build_excel_dataset_sql(dataset, datasource, limit)

    table = _source_table(dataset)
    dimension_specs = _dimension_specs(dataset, table)
    fields = [item["field"] for item in dimension_specs]
    metric_specs = _metric_specs(dataset)
    aggregations = [item["expression"] for item in metric_specs]
    aggregation_fields = _aggregation_field_refs(aggregations, table)
    params: dict[str, Any] = {}
    if limit is not None:
        params["limit"] = _clamp_preview_limit(limit)
    engine = get_datasource_engine(datasource.database_url)

    validation_fields = [field for field in fields if not field.endswith(".*")]
    validation_fields.extend(field for field in aggregation_fields)
    for expression in _derived_expressions(dataset):
        validation_fields.extend(
            re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*\b", expression)
        )
    _validate_database_table_and_columns(engine, table, validation_fields)

    select_parts: list[str] = []
    group_by_parts: list[str] = []
    for spec in dimension_specs:
        field = str(spec["field"])
        if field.endswith(".*"):
            if aggregations:
                continue
            select_parts.append("*")
            continue
        if aggregations and _normalized_field_ref(field, table) in aggregation_fields and not spec.get("explicit_dimension"):
            continue
        alias = spec["alias"] or _field_alias(field, table)
        column_ref = _quote_column_ref(engine, field, table)
        select_parts.append(f"{column_ref} AS {_quote_output_alias(engine, alias)}")
        if aggregations:
            group_by_parts.append(column_ref)

    for expression in _derived_expressions(dataset):
        select_parts.append(_render_derived_expression(engine, expression, table))

    for spec in metric_specs:
        select_parts.append(_render_aggregation(engine, str(spec["expression"]), table, spec["alias"]))

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
    if limit is not None:
        sql_parts.append("LIMIT :limit")
    return "\n".join(sql_parts), params


def _execute_dataset_preview(dataset: Dataset, datasource: DataSource, limit: int) -> dict[str, Any]:
    if (
        settings.doris_enabled
        and dataset.materialization_status == "ready"
        and dataset.materialized_table_name
    ):
        return execute_materialized_dataset_preview(dataset.materialized_table_name, limit)

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


def _execute_dataset_extract(dataset: Dataset, datasource: DataSource) -> dict[str, Any]:
    limit = settings.doris_materialization_limit if settings.doris_materialization_limit > 0 else None
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


def _session_has_table(db: Session, table_name: str) -> bool:
    bind = db.get_bind() if hasattr(db, "get_bind") else None
    if bind is None:
        return True
    try:
        return inspect(db.connection()).has_table(table_name)
    except Exception:
        return True


def _sync_dataset_asset(db: Session, dataset: Dataset) -> None:
    if not _session_has_table(db, DataAsset.__tablename__):
        return
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
        "dimensions": _dataset_dimension_fields(dataset),
        "filters": dataset.filters_json,
        "derived_columns": dataset.derived_columns_json,
        "joins": dataset.joins_json,
        "aggregations": dataset.aggregations_json,
        "metrics": _aggregation_expressions(dataset),
        "semantic_model": dataset.semantic_model_json,
    }
    db.flush()
    _sync_dataset_lineage(db, dataset, asset)


def _sync_dataset_lineage(db: Session, dataset: Dataset, dataset_asset: DataAsset) -> None:
    """Auto-create lineage: datasource table asset → dataset asset."""
    try:
        if not _session_has_table(db, AssetLineage.__tablename__):
            return
        if not dataset.datasource_id:
            return
        fields_json = dataset.fields_json or {}
        table_name = fields_json.get("table") if isinstance(fields_json, dict) else None
        if not table_name:
            return
        table_asset = (
            db.query(DataAsset)
            .filter(
                DataAsset.asset_type == "table",
                DataAsset.datasource_id == dataset.datasource_id,
                DataAsset.name == table_name,
            )
            .first()
        )
        if not table_asset:
            return
        existing = (
            db.query(AssetLineage)
            .filter(AssetLineage.source_id == table_asset.id, AssetLineage.target_id == dataset_asset.id)
            .first()
        )
        if not existing:
            db.add(AssetLineage(
                source_id=table_asset.id,
                target_id=dataset_asset.id,
                rel_type="derives_from",
                org_id=dataset.org_id,
            ))
    except Exception:
        pass  # lineage is best-effort, never block the main flow


def _notify_dataset_refresh(db: Session, dataset: Dataset) -> None:
    """Notify subscribers after a dataset data refresh."""
    try:
        if not _session_has_table(db, DataAsset.__tablename__):
            return
        asset = (
            db.query(DataAsset)
            .filter(DataAsset.asset_type == "dataset", DataAsset.asset_id == dataset.id)
            .first()
        )
        if not asset:
            return
        from app.api.catalog import _notify_subscribers
        _notify_subscribers(db, asset.id, f"数据集「{dataset.name}」数据已更新")
        db.commit()
    except Exception:
        pass


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
    values = payload.model_dump(exclude={"org_id", "owner_id"})
    values["fields_json"] = _normalize_fields_json(values.get("fields_json"))
    _normalize_model_values(values)
    approval_required = _apply_dataset_publication_workflow(values, current_user)
    dataset = Dataset(
        **values,
        org_id=org_id,
        owner_id=payload.owner_id or current_user.id,
    )
    db.add(dataset)
    db.flush()
    _sync_dataset_publication_state(db, dataset)
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
        message="数据集已提交审批" if approval_required else "数据集已创建",
        detail={
            "datasource_id": dataset.datasource_id,
            "status": dataset.status,
            "visibility": dataset.visibility,
            "approval_required": approval_required,
        },
    )
    return dataset


@router.get("/{dataset_id}", response_model=DatasetOut)
def get_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _get_dataset_for_user(db, dataset_id, current_user)


@router.get("/{dataset_id}/semantic-model", response_model=DatasetSemanticModelResponse)
def get_dataset_semantic_model(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = _get_dataset_for_user(db, dataset_id, current_user)
    try:
        semantic_model = infer_semantic_model(dataset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"dataset_id": dataset.id, "semantic_model": semantic_model}


@router.post("/{dataset_id}/validate-semantic-model", response_model=DatasetSemanticModelValidationResponse)
def validate_dataset_semantic_model(
    dataset_id: int,
    payload: DatasetSemanticModelUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = _get_dataset_for_user(db, dataset_id, current_user)
    try:
        semantic_model = normalize_semantic_model(payload.semantic_model, dataset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"dataset_id": dataset.id, "semantic_model": semantic_model, "valid": True}


@router.put("/{dataset_id}/semantic-model", response_model=DatasetSemanticModelResponse)
def update_dataset_semantic_model(
    dataset_id: int,
    payload: DatasetSemanticModelUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")
    if not _can_manage_dataset(current_user, dataset):
        raise HTTPException(status_code=403, detail="无权限")
    try:
        semantic_model = normalize_semantic_model(payload.semantic_model, dataset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    dataset.semantic_model_json = semantic_model
    if dataset.status == "published":
        _sync_dataset_asset(db, dataset)
    db.commit()
    db.refresh(dataset)
    try_record_audit_log(
        db,
        actor=current_user,
        action="dataset.semantic_model.update",
        resource_type="dataset",
        resource_id=dataset.id,
        resource_name=dataset.name,
        org_id=dataset.org_id,
        message="数据集语义层已更新",
        detail={
            "dimensions": len(semantic_model["dimensions"]),
            "metrics": len(semantic_model["metrics"]),
            "time_dimensions": len(semantic_model["time_dimensions"]),
        },
    )
    return {"dataset_id": dataset.id, "semantic_model": semantic_model}


@router.post("/ai-config/suggest", response_model=DatasetAIConfigSuggestResponse)
async def suggest_dataset_ai_config(
    payload: DatasetAIConfigSuggestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = None
    if payload.dataset_id:
        dataset = _get_dataset_for_user(db, payload.dataset_id, current_user)
        datasource = _get_datasource_for_user(db, dataset.datasource_id, current_user)
    else:
        if not payload.datasource_id:
            raise HTTPException(status_code=400, detail="请选择数据源或数据集")
        datasource = _get_datasource_for_user(db, payload.datasource_id, current_user)

    response = await build_dataset_ai_config(
        datasource=datasource,
        dataset=dataset,
        table=payload.table,
        fields_json=payload.fields_json,
        aggregations_json=payload.aggregations_json,
        semantic_model_json=payload.semantic_model_json,
        drill_config_json=payload.drill_config_json,
    )
    try_record_audit_log(
        db,
        actor=current_user,
        action="dataset.ai_config.suggest",
        resource_type="dataset" if dataset else "datasource",
        resource_id=dataset.id if dataset else datasource.id,
        resource_name=dataset.name if dataset else datasource.name,
        org_id=dataset.org_id if dataset else datasource.org_id,
        message="数据集 AI 建模草稿已生成",
        detail={
            "source": response.get("source"),
            "dimensions": len(response.get("semantic_model", {}).get("dimensions", [])),
            "metrics": len(response.get("semantic_model", {}).get("metrics", [])),
            "paths": len(response.get("drill_config", {}).get("paths", [])),
        },
    )
    return response


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


@router.post("/preview-draft", response_model=DatasetPreviewResponse)
def preview_dataset_draft(
    payload: DatasetDraftPreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_values(payload.status, payload.visibility)
    datasource = _get_datasource_for_user(db, payload.datasource_id, current_user)
    org_id = payload.org_id if current_user.role == "super_admin" and payload.org_id else datasource.org_id
    values = payload.model_dump(exclude={"org_id", "owner_id", "limit"})
    values["fields_json"] = _normalize_fields_json(values.get("fields_json"))
    dataset = Dataset(
        **values,
        org_id=org_id,
        owner_id=payload.owner_id or current_user.id,
    )
    limit = _clamp_preview_limit(payload.limit)
    try:
        preview = _execute_dataset_preview(dataset, datasource, limit)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"数据集预览失败: {exc}")

    return jsonable_encoder(
        {
            "dataset_id": 0,
            "columns": preview.get("columns", []),
            "rows": preview.get("rows", []),
            "row_count": len(preview.get("rows", [])),
        }
    )


@router.post("/{dataset_id}/materialize", response_model=DatasetOut)
def materialize_dataset(
    dataset_id: int,
    payload: DatasetMaterializeRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not settings.doris_enabled:
        raise HTTPException(status_code=400, detail="Doris 未启用")
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")
    if not _can_manage_dataset(current_user, dataset):
        raise HTTPException(status_code=403, detail="无权限")
    datasource = _get_datasource_for_user(db, dataset.datasource_id, current_user)
    request = payload or DatasetMaterializeRequest()
    mode = request.mode or "full"
    if mode not in {"full", "incremental"}:
        raise HTTPException(status_code=400, detail="物化模式必须为 full 或 incremental")

    now = datetime.utcnow()
    dataset.materialization_status = "running"
    dataset.materialization_mode = mode
    dataset.incremental_key = request.incremental_key or dataset.incremental_key
    db.flush()

    try:
        extract = _execute_dataset_extract(dataset, datasource)
        result = write_dataset_to_olap(
            dataset,
            extract.get("columns", []),
            extract.get("rows", []),
            mode=mode,
            incremental_key=dataset.incremental_key,
        )
        dataset.materialization_status = "ready"
        dataset.materialization_mode = result.mode
        dataset.materialized_table_name = result.table_name
        dataset.materialized_at = now
        dataset.incremental_watermark = result.watermark or dataset.incremental_watermark
        dataset.materialization_message = result.message
        dataset.last_refresh_status = "success"
        dataset.last_refresh_at = now
        dataset.last_refresh_row_count = result.row_count
        log = DatasetRefreshLog(
            dataset_id=dataset.id,
            status="success",
            row_count=result.row_count,
            message=result.message,
            org_id=dataset.org_id,
            triggered_by_id=current_user.id,
        )
        db.add(log)
        db.commit()
        db.refresh(dataset)
        _notify_dataset_refresh(db, dataset)
        try_record_audit_log(
            db,
            actor=current_user,
            action="dataset.materialize",
            resource_type="dataset",
            resource_id=dataset.id,
            resource_name=dataset.name,
            org_id=dataset.org_id,
            message="数据集已物化到 Doris",
            detail={"mode": result.mode, "row_count": result.row_count, "table_name": result.table_name},
        )
        return dataset
    except HTTPException:
        raise
    except Exception as exc:
        message = f"Doris 物化失败: {exc}"
        dataset.materialization_status = "error"
        dataset.materialization_message = message
        dataset.last_refresh_status = "error"
        dataset.last_refresh_at = now
        log = DatasetRefreshLog(
            dataset_id=dataset.id,
            status="error",
            row_count=0,
            message=message,
            org_id=dataset.org_id,
            triggered_by_id=current_user.id,
        )
        db.add(log)
        db.commit()
        try_record_audit_log(
            db,
            actor=current_user,
            action="dataset.materialize",
            resource_type="dataset",
            resource_id=dataset.id,
            resource_name=dataset.name,
            org_id=dataset.org_id,
            status="error",
            message=message,
        )
        raise HTTPException(status_code=400, detail=message)


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
    if "fields_json" in values:
        values["fields_json"] = _normalize_fields_json(values.get("fields_json"))
    _normalize_model_values(values, dataset)
    if "datasource_id" in values:
        datasource = _get_datasource_for_user(db, values["datasource_id"], current_user)
        if current_user.role != "super_admin":
            dataset.org_id = datasource.org_id
    approval_required = _apply_dataset_publication_workflow(values, current_user, dataset)
    for key, value in values.items():
        setattr(dataset, key, value)
    _sync_dataset_publication_state(db, dataset)
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
        message="数据集已提交审批" if approval_required else "数据集已更新",
        detail={"fields": list(values.keys()), "approval_required": approval_required},
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
    dataset.visibility = DATASET_VISIBILITY_ORG
    approval_required = _requires_org_visibility_approval(
        current_user,
        dataset.visibility,
        DATASET_STATUS_PUBLISHED,
    )
    dataset.status = DATASET_STATUS_PENDING_REVIEW if approval_required else DATASET_STATUS_PUBLISHED
    _sync_dataset_publication_state(db, dataset)
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
        message="数据集已提交审批" if approval_required else "数据集已发布",
        detail={"approval_required": approval_required},
    )
    return dataset


@router.post("/{dataset_id}/approve", response_model=DatasetOut)
def approve_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")
    if not _can_approve_dataset(db, current_user, dataset):
        raise HTTPException(status_code=403, detail="需要同部门部门管理员或以上权限")
    if dataset.visibility != DATASET_VISIBILITY_ORG:
        raise HTTPException(status_code=400, detail="仅组织内可见的数据集需要审批")

    dataset.status = DATASET_STATUS_PUBLISHED
    dataset.visibility = DATASET_VISIBILITY_ORG
    _sync_dataset_publication_state(db, dataset)
    db.commit()
    db.refresh(dataset)
    try_record_audit_log(
        db,
        actor=current_user,
        action="dataset.approve",
        resource_type="dataset",
        resource_id=dataset.id,
        resource_name=dataset.name,
        org_id=dataset.org_id,
        message="数据集已审批发布",
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
    assert_dataset_can_delete(db, dataset)
    dataset_name = dataset.name
    dataset_org_id = dataset.org_id
    delete_catalog_asset(db, "dataset", dataset.id)
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
