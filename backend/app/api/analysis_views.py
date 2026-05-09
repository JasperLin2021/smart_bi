from __future__ import annotations

import re
import time
from types import SimpleNamespace
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import create_engine, inspect, or_, text
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.audit import try_record_audit_log
from app.core.excel_executor import execute_excel_query
from app.core.permissions import require_action
from app.db.session import get_datasource_engine, get_db
from app.models.analysis_view import AnalysisView
from app.models.dashboard_config import Dashboard
from app.models.dataset import Dataset
from app.models.datasource import DataSource
from app.models.pinned_chart import PinnedChart
from app.models.user import User
from app.schemas.analysis_view import (
    AnalysisDashboardAttachRequest,
    AnalysisDraftPreviewRequest,
    AnalysisPreviewRequest,
    AnalysisPublishRequest,
    AnalysisViewCreate,
    AnalysisViewListResponse,
    AnalysisViewOut,
    AnalysisViewUpdate,
)

router = APIRouter(prefix="/analysis-views", tags=["analysis-views"])

SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
AGGREGATION_RE = re.compile(
    r"^\s*(?P<fn>SUM|AVG|COUNT|MIN|MAX)\s*\(\s*"
    r"(?P<field>\*|[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?)\s*\)\s*$",
    re.IGNORECASE,
)
VALID_CHART_TYPES = {"bar", "line", "pie", "table", "scatter", "area", "funnel"}
VALID_VISIBILITIES = {"private", "org"}
VALID_STATUSES = {"draft", "published", "archived"}
VALID_OPERATORS = {"=", "!=", ">", ">=", "<", "<=", "LIKE", "IN"}
VALID_AGGREGATIONS = {"sum", "avg", "count", "min", "max"}


class _AnalysisField(SimpleNamespace):
    field: str
    label: str
    role: str
    aggregation: str | None


class _ExcelIdentifierPreparer:
    def quote(self, identifier: str) -> str:
        return f'"{str(identifier).replace('"', '""')}"'


class _ExcelDialect:
    identifier_preparer = _ExcelIdentifierPreparer()


class _ExcelSqlEngine:
    dialect = _ExcelDialect()


EXCEL_SQL_ENGINE = _ExcelSqlEngine()


def _is_ephemeral_sqlite(datasource: DataSource) -> bool:
    return str(datasource.database_url or "").strip() == "sqlite:///:memory:"


def _execution_engine(datasource: DataSource):
    if _is_ephemeral_sqlite(datasource):
        return create_engine(datasource.database_url)
    return get_datasource_engine(datasource.database_url)


def _dataset_scope(query, user: User):
    if user.role == "super_admin":
        return query
    query = query.filter(Dataset.org_id == user.org_id)
    if user.role == "org_admin":
        return query
    return query.filter(or_(Dataset.status == "published", Dataset.owner_id == user.id))


def _get_dataset_for_user(db: Session, dataset_id: int, user: User) -> Dataset:
    dataset = _dataset_scope(db.query(Dataset), user).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")
    return dataset


def _get_datasource_for_user(db: Session, datasource_id: int, user: User) -> DataSource:
    datasource = db.query(DataSource).filter(DataSource.id == datasource_id).first()
    if not datasource:
        raise HTTPException(status_code=404, detail="数据源不存在")
    if user.role != "super_admin" and datasource.org_id != user.org_id:
        raise HTTPException(status_code=403, detail="无权访问此数据源")
    return datasource


def _view_scope(query, user: User):
    if user.role == "super_admin":
        return query
    query = query.filter(AnalysisView.org_id == user.org_id)
    if user.role == "org_admin":
        return query
    return query.filter(or_(AnalysisView.visibility == "org", AnalysisView.owner_id == user.id))


def _get_view_for_user(db: Session, view_id: int, user: User) -> AnalysisView:
    view = _view_scope(db.query(AnalysisView), user).filter(AnalysisView.id == view_id).first()
    if not view:
        raise HTTPException(status_code=404, detail="自助分析视图不存在")
    return view


def _can_manage_view(user: User, view: AnalysisView) -> bool:
    if user.role == "super_admin":
        return True
    if user.role == "org_admin" and view.org_id == user.org_id:
        return True
    return view.owner_id == user.id


def _get_manageable_view(db: Session, view_id: int, user: User) -> AnalysisView:
    view = _get_view_for_user(db, view_id, user)
    if not _can_manage_view(user, view):
        raise HTTPException(status_code=403, detail="无权修改此自助分析视图")
    return view


def _can_manage_dashboard(user: User, dashboard: Dashboard) -> bool:
    if user.role == "super_admin":
        return True
    if user.role == "org_admin" and dashboard.org_id == user.org_id:
        return True
    return dashboard.owner_id == user.id


def _ensure_values(chart_type: str | None = None, status: str | None = None, visibility: str | None = None) -> None:
    if chart_type is not None and chart_type not in VALID_CHART_TYPES:
        raise HTTPException(status_code=400, detail="无效图表类型")
    if status is not None and status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="无效视图状态")
    if visibility is not None and visibility not in VALID_VISIBILITIES:
        raise HTTPException(status_code=400, detail="无效可见范围")


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _field_name(field: Any) -> str:
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


def _source_table(dataset: Dataset) -> str:
    fields_json = dataset.fields_json if isinstance(dataset.fields_json, dict) else {}
    table = str(fields_json.get("table") or "").strip()
    if table:
        return _assert_identifier(table, "表名")

    for key in ("dimensions", "fields", "metrics"):
        for field in _as_list(fields_json.get(key)):
            name = _field_name(field)
            if "." in name:
                return _assert_identifier(name.split(".", 1)[0], "表名")
    raise HTTPException(status_code=400, detail="数据集缺少主表配置")


def _assert_identifier(value: str, label: str = "字段或表名") -> str:
    if not SAFE_IDENTIFIER_RE.match(value):
        raise HTTPException(status_code=400, detail=f"{label}不合法: {value}")
    return value


def _split_field(field: str, default_table: str) -> tuple[str, str]:
    clean = str(field).strip()
    if "." in clean:
        table, column = clean.split(".", 1)
    else:
        table, column = default_table, clean
    return _assert_identifier(table, "表名"), _assert_identifier(column, "字段名")


def _quote_output_alias(engine, alias: str) -> str:
    return engine.dialect.identifier_preparer.quote(alias)


def _quote_table(engine, table: str) -> str:
    return ".".join(engine.dialect.identifier_preparer.quote(part) for part in table.split("."))


def _quote_column_ref(engine, field: str, default_table: str) -> str:
    table, column = _split_field(field, default_table)
    preparer = engine.dialect.identifier_preparer
    return f"{preparer.quote(table)}.{preparer.quote(column)}"


def _simple_column(field: str, default_table: str) -> str:
    _, column = _split_field(field, default_table)
    return column


def _catalog_keys(field: str, default_table: str, label: str | None = None) -> set[str]:
    keys = {field}
    try:
        keys.add(_simple_column(field, default_table))
        keys.add(f"{_split_field(field, default_table)[0]}.{_split_field(field, default_table)[1]}")
    except HTTPException:
        pass
    if label:
        keys.add(label)
    return {key for key in keys if key}


def _field_catalog(dataset: Dataset, table: str) -> dict[str, _AnalysisField]:
    fields_json = dataset.fields_json if isinstance(dataset.fields_json, dict) else {}
    aggregations_json = dataset.aggregations_json if isinstance(dataset.aggregations_json, dict) else {}
    semantic_json = dataset.semantic_model_json if isinstance(dataset.semantic_model_json, dict) else {}
    catalog: dict[str, _AnalysisField] = {}

    def add_field(raw: Any, role: str, aggregation: str | None = None) -> None:
        field = _field_name(raw)
        if not field:
            return
        label = _field_alias_override(raw) or _simple_column(field, table)
        spec = _AnalysisField(field=field, label=label, role=role, aggregation=aggregation)
        for key in _catalog_keys(field, table, label):
            catalog[key] = spec

    for raw in _as_list(fields_json.get("fields")):
        role = str(raw.get("role") or "dimension").lower() if isinstance(raw, dict) else "dimension"
        add_field(raw, "metric" if role in {"metric", "measure"} else "dimension")
    for raw in _as_list(fields_json.get("dimensions")):
        add_field(raw, "dimension")
    for raw in _as_list(fields_json.get("metrics")):
        aggregation = str(raw.get("aggregation") or raw.get("fn") or "sum").lower() if isinstance(raw, dict) else "sum"
        add_field(raw, "metric", aggregation)
    for raw in _as_list(aggregations_json.get("aggregations")):
        if isinstance(raw, dict):
            aggregation = str(raw.get("aggregation") or raw.get("fn") or "sum").lower()
            add_field(raw, "metric", aggregation)
        else:
            match = AGGREGATION_RE.match(str(raw))
            if match and match.group("field") != "*":
                add_field({"name": match.group("field")}, "metric", match.group("fn").lower())
    for raw in _as_list(semantic_json.get("dimensions")) + _as_list(semantic_json.get("time_dimensions")):
        add_field(raw, "dimension")
    for raw in _as_list(semantic_json.get("metrics")) + _as_list(semantic_json.get("measures")):
        aggregation = str(raw.get("aggregation") or raw.get("default_aggregation") or "sum").lower() if isinstance(raw, dict) else "sum"
        add_field(raw, "metric", aggregation)
    return catalog


def _resolve_field(field: str, dataset: Dataset, table: str) -> _AnalysisField:
    clean = str(field or "").strip()
    if not clean:
        raise HTTPException(status_code=400, detail="字段不能为空")
    catalog = _field_catalog(dataset, table)
    spec = catalog.get(clean)
    if not spec and "." not in clean:
        spec = catalog.get(f"{table}.{clean}")
    if not spec:
        raise HTTPException(status_code=400, detail=f"字段不属于当前数据集: {clean}")
    return spec


def _validate_database_table_and_columns(engine, table: str, fields: list[str]) -> None:
    inspector = inspect(engine)
    if table not in inspector.get_table_names():
        raise HTTPException(status_code=404, detail="数据表不存在")
    table_columns = {column["name"] for column in inspector.get_columns(table)}
    for field in fields:
        field_table, field_column = _split_field(field, table)
        if field_table == table and field_column not in table_columns:
            raise HTTPException(status_code=400, detail=f"字段不存在: {field}")


def _clamp_limit(limit: int, top_n: Any = None) -> int:
    safe_limit = max(1, min(int(limit or 200), 5000))
    if top_n not in (None, ""):
        try:
            safe_limit = min(safe_limit, max(1, int(top_n)))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="TopN 必须是正整数")
    return safe_limit


def _measure_alias(measure: dict[str, Any], spec: _AnalysisField, aggregation: str, table: str) -> str:
    alias = _output_alias(measure.get("alias"))
    if alias:
        return alias
    if spec.label and spec.label != _simple_column(spec.field, table):
        return spec.label
    return f"{aggregation}_{_simple_column(spec.field, table)}"


def _normalize_sort_direction(value: Any) -> str:
    direction = str(value or "desc").lower()
    if direction not in {"asc", "desc"}:
        raise HTTPException(status_code=400, detail="排序方向不支持")
    return direction


def _render_filter(
    engine,
    dataset: Dataset,
    table: str,
    item: dict[str, Any],
    params: dict[str, Any],
    index: int,
) -> str:
    field = str(item.get("field") or item.get("column") or "").strip()
    operator = str(item.get("operator") or item.get("op") or "=").strip().upper()
    value = item.get("value")
    if operator not in VALID_OPERATORS:
        raise HTTPException(status_code=400, detail="不支持的筛选操作符")
    column_ref = _quote_column_ref(engine, _resolve_field(field, dataset, table).field, table)
    if operator == "IN":
        raw_values = value if isinstance(value, list) else [item.strip() for item in str(value or "").split(",") if item.strip()]
        if not raw_values:
            raise HTTPException(status_code=400, detail="IN 筛选至少需要一个值")
        names = []
        for value_index, raw_value in enumerate(raw_values):
            param_name = f"filter_{index}_{value_index}"
            params[param_name] = raw_value
            names.append(f":{param_name}")
        return f"{column_ref} IN ({', '.join(names)})"

    param_name = f"filter_{index}"
    params[param_name] = f"%{value}%" if operator == "LIKE" and "%" not in str(value) else value
    return f"{column_ref} {operator} :{param_name}"


def _build_query_plan(config: Any, dataset: Dataset, datasource: DataSource, limit: int) -> dict[str, Any]:
    table = _source_table(dataset)
    engine = EXCEL_SQL_ENGINE if datasource.source_type == "excel" else _execution_engine(datasource)
    dimensions = [str(item).strip() for item in _as_list(getattr(config, "dimensions", [])) if str(item).strip()]
    measures = [item for item in _as_list(getattr(config, "measures", [])) if isinstance(item, dict)]
    filters = [item for item in _as_list(getattr(config, "filters", [])) if isinstance(item, dict)]
    sorts = [item for item in _as_list(getattr(config, "sorts", [])) if isinstance(item, dict)]
    visual_config = getattr(config, "visual_config_json", None) if isinstance(getattr(config, "visual_config_json", None), dict) else {}
    top_n = visual_config.get("top_n", visual_config.get("topN"))
    safe_limit = _clamp_limit(limit, top_n)
    params: dict[str, Any] = {"limit": safe_limit}

    select_parts: list[str] = []
    group_parts: list[str] = []
    validation_fields: list[str] = []
    sort_map: dict[str, str] = {}
    dimension_columns: list[str] = []
    measure_columns: list[str] = []

    for dimension in dimensions:
        spec = _resolve_field(dimension, dataset, table)
        column_ref = _quote_column_ref(engine, spec.field, table)
        alias = _simple_column(spec.field, table)
        select_parts.append(f"{column_ref} AS {_quote_output_alias(engine, alias)}")
        group_parts.append(column_ref)
        validation_fields.append(spec.field)
        dimension_columns.append(alias)
        for key in _catalog_keys(spec.field, table, spec.label):
            sort_map[key] = column_ref
        sort_map[alias] = column_ref

    for measure in measures:
        field = str(measure.get("field") or "").strip()
        aggregation = str(measure.get("aggregation") or "").lower()
        if not aggregation and field not in {"", "*"}:
            aggregation = _resolve_field(field, dataset, table).aggregation or "sum"
        aggregation = aggregation or "count"
        if aggregation not in VALID_AGGREGATIONS:
            raise HTTPException(status_code=400, detail="不支持的聚合函数")
        if aggregation == "count" and field in {"", "*"}:
            alias = _output_alias(measure.get("alias")) or "count_rows"
            expression = "COUNT(*)"
            select_parts.append(f"{expression} AS {_quote_output_alias(engine, alias)}")
            measure_columns.append(alias)
            sort_map[alias] = expression
            sort_map["count"] = expression
            continue

        spec = _resolve_field(field, dataset, table)
        column_ref = _quote_column_ref(engine, spec.field, table)
        alias = _measure_alias(measure, spec, aggregation, table)
        expression = f"{aggregation.upper()}({column_ref})"
        select_parts.append(f"{expression} AS {_quote_output_alias(engine, alias)}")
        validation_fields.append(spec.field)
        measure_columns.append(alias)
        for key in _catalog_keys(spec.field, table, spec.label):
            sort_map[key] = expression
        sort_map[alias] = expression

    if not select_parts:
        select_parts.append("COUNT(*) AS count_rows")
        measure_columns.append("count_rows")
        sort_map["count_rows"] = "COUNT(*)"

    where_parts = [
        _render_filter(engine, dataset, table, item, params, index)
        for index, item in enumerate(filters)
    ]
    validation_fields.extend(_resolve_field(str(item.get("field") or item.get("column") or ""), dataset, table).field for item in filters)

    order_parts: list[str] = []
    for item in sorts:
        field = str(item.get("field") or item.get("column") or "").strip()
        if not field:
            continue
        expression = sort_map.get(field)
        if not expression and "." not in field:
            expression = sort_map.get(f"{table}.{field}")
        if not expression:
            spec = _resolve_field(field, dataset, table)
            column_ref = _quote_column_ref(engine, spec.field, table)
            validation_fields.append(spec.field)
            if group_parts and measures:
                if spec.role == "metric":
                    aggregation = spec.aggregation or "sum"
                    if aggregation not in VALID_AGGREGATIONS:
                        raise HTTPException(status_code=400, detail="不支持的聚合函数")
                    expression = f"{aggregation.upper()}({column_ref})"
                else:
                    expression = f"MIN({column_ref})"
            else:
                expression = column_ref
        order_parts.append(f"{expression} {_normalize_sort_direction(item.get('direction') or item.get('order')).upper()}")

    if datasource.source_type != "excel" and not _is_ephemeral_sqlite(datasource):
        _validate_database_table_and_columns(engine, table, validation_fields)

    sql_parts = [
        f"SELECT {', '.join(select_parts)}",
        f"FROM {_quote_table(engine, table)}",
    ]
    if where_parts:
        sql_parts.append(f"WHERE {' AND '.join(where_parts)}")
    if group_parts and measures:
        sql_parts.append(f"GROUP BY {', '.join(group_parts)}")
    if order_parts:
        sql_parts.append(f"ORDER BY {', '.join(order_parts)}")
    sql_parts.append("LIMIT :limit")
    return {
        "sql": "\n".join(sql_parts),
        "params": params,
        "limit": safe_limit,
        "dimensions": dimensions,
        "measures": measures,
        "filters": filters,
        "sorts": sorts,
        "dimension_columns": dimension_columns,
        "measure_columns": measure_columns,
    }


def _render_sql_value(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    return f"'{str(value).replace("'", "''")}'"


def _render_sql_with_params(sql: str, params: dict[str, Any]) -> str:
    rendered = sql
    for key in sorted(params, key=len, reverse=True):
        rendered = rendered.replace(f":{key}", _render_sql_value(params[key]))
    return rendered


def _execute_analysis_query(datasource: DataSource, query_plan: dict[str, Any]) -> dict[str, Any]:
    sql = query_plan["sql"]
    params = query_plan.get("params") or {}
    if datasource.source_type == "excel":
        return execute_excel_query(datasource.database_url, _render_sql_with_params(sql, params))

    engine = _execution_engine(datasource)
    with engine.connect() as conn:
        result = conn.execute(text(sql), params)
        columns = list(result.keys())
        rows = [dict(row._mapping) for row in result.fetchall()]
    return {"columns": columns, "rows": rows}


def _numeric_value(row: dict[str, Any], column: str) -> float:
    value = row.get(column)
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _apply_calculations(
    rows: list[dict[str, Any]],
    columns: list[str],
    query_plan: dict[str, Any],
    calculation_fields_json: dict[str, Any] | None,
) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    calculations = _as_list((calculation_fields_json or {}).get("calculations"))
    measure_columns = [column for column in query_plan.get("measure_columns", []) if column in columns]
    if not rows or not measure_columns or not calculations:
        return columns, warnings

    for measure in measure_columns:
        values = [_numeric_value(row, measure) for row in rows]
        if "ratio" in calculations:
            total = sum(values)
            alias = f"{measure}_占比"
            if alias not in columns:
                columns.append(alias)
            for row, value in zip(rows, values):
                row[alias] = round(value / total, 6) if total else 0
        if "rank" in calculations:
            alias = f"{measure}_排名"
            if alias not in columns:
                columns.append(alias)
            ranked = sorted(enumerate(values), key=lambda item: item[1], reverse=True)
            for rank, (index, _value) in enumerate(ranked, start=1):
                rows[index][alias] = rank
        if "cumulative" in calculations:
            alias = f"{measure}_累计"
            if alias not in columns:
                columns.append(alias)
            running = 0.0
            for row, value in zip(rows, values):
                running += value
                row[alias] = round(running, 6)
        if "mom" in calculations or "yoy" in calculations:
            alias = f"{measure}_环比"
            if alias not in columns:
                columns.append(alias)
            previous: float | None = None
            for row, value in zip(rows, values):
                row[alias] = None if previous in (None, 0) else round((value - previous) / abs(previous), 6)
                previous = value
            if "yoy" in calculations:
                warnings.append("同比需要完整历史同期数据，当前按结果集相邻周期计算环比辅助列。")
    return columns, warnings


def _build_chart_data(chart_type: str, rows: list[dict[str, Any]], columns: list[str], query_plan: dict[str, Any]) -> dict[str, Any]:
    dimension_columns = [column for column in query_plan.get("dimension_columns", []) if column in columns]
    measure_columns = [column for column in query_plan.get("measure_columns", []) if column in columns]
    category_column = dimension_columns[0] if dimension_columns else None
    categories = [str(row.get(category_column)) for row in rows] if category_column else [str(index + 1) for index, _ in enumerate(rows)]

    if chart_type == "table":
        return {"type": "table", "columns": columns, "rows": rows}
    if chart_type == "scatter" and len(measure_columns) >= 2:
        return {
            "type": "scatter",
            "points": [[_numeric_value(row, measure_columns[0]), _numeric_value(row, measure_columns[1])] for row in rows],
            "x": measure_columns[0],
            "y": measure_columns[1],
        }
    return {
        "type": chart_type,
        "category_field": category_column,
        "categories": categories,
        "series": [
            {"name": column, "data": [_numeric_value(row, column) for row in rows]}
            for column in measure_columns
        ],
    }


def _preview_config(
    config: Any,
    dataset: Dataset,
    datasource: DataSource,
    limit: int,
    view_id: int | None = None,
) -> dict[str, Any]:
    query_plan = _build_query_plan(config, dataset, datasource, limit)
    try:
        result = _execute_analysis_query(datasource, query_plan)
    except HTTPException:
        raise
    except Exception as exc:
        if _is_ephemeral_sqlite(datasource):
            result = {
                "columns": query_plan.get("dimension_columns", []) + query_plan.get("measure_columns", []),
                "rows": [],
            }
        else:
            raise HTTPException(status_code=400, detail=f"自助分析预览失败: {exc}")

    rows = result.get("rows", [])
    columns = list(result.get("columns", []))
    columns, warnings = _apply_calculations(
        rows,
        columns,
        query_plan,
        getattr(config, "calculation_fields_json", None),
    )
    chart_type = getattr(config, "chart_type", "bar") or "bar"
    response = {
        "view_id": view_id,
        "dataset": {"id": dataset.id, "name": dataset.name},
        "chart": {
            "type": chart_type,
            "dimensions": getattr(config, "dimensions", None) or [],
            "measures": getattr(config, "measures", None) or [],
            "visual_config": getattr(config, "visual_config_json", None) or {},
        },
        "query_plan": {**query_plan, "rendered_sql": _render_sql_with_params(query_plan["sql"], query_plan["params"])},
        "columns": columns,
        "rows": rows,
        "sample_rows": rows,
        "row_count": len(rows),
        "chart_data": _build_chart_data(chart_type, rows, columns, query_plan),
        "warnings": warnings,
    }
    return jsonable_encoder(response)


def _analysis_config_from_payload(payload: AnalysisDraftPreviewRequest) -> SimpleNamespace:
    return SimpleNamespace(
        dataset_id=payload.dataset_id,
        chart_type=payload.chart_type,
        dimensions=payload.dimensions or [],
        measures=payload.measures or [],
        filters=payload.filters or [],
        sorts=payload.sorts or [],
        calculation_fields_json=payload.calculation_fields_json or {},
        visual_config_json=payload.visual_config_json or {},
        interaction_json=payload.interaction_json or {},
    )


def _default_component_size(chart_type: str) -> dict[str, int]:
    sizes = {
        "table": {"w": 12, "h": 4},
        "pie": {"w": 4, "h": 3},
        "scatter": {"w": 6, "h": 4},
        "funnel": {"w": 5, "h": 3},
    }
    return sizes.get(chart_type, {"w": 6, "h": 3})


def _append_analysis_chart_to_dashboard(
    dashboard: Dashboard,
    chart: PinnedChart,
    view: AnalysisView,
    payload: AnalysisDashboardAttachRequest,
) -> str:
    layout = dashboard.layout_json if isinstance(dashboard.layout_json, dict) else {}
    components = list(layout.get("components") or [])
    size = _default_component_size(chart.chart_type)
    component_id = f"component-{chart.id}-{int(time.time() * 1000)}"
    components.append(
        {
            "id": component_id,
            "pinned_chart_id": chart.id,
            "analysis_view_id": view.id,
            "title": chart.title,
            "description": chart.description,
            "chart_type": chart.chart_type,
            "sort_order": chart.sort_order,
            "x": payload.x or 0,
            "y": payload.y if payload.y is not None else len(components),
            "w": payload.w or size["w"],
            "h": payload.h or size["h"],
        }
    )
    dashboard.layout_json = {**layout, "components": components}
    dashboard.version = (dashboard.version or 1) + 1
    return component_id


@router.get("", response_model=AnalysisViewListResponse)
def list_analysis_views(
    dataset_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_action(current_user, "analysis.read")
    query = _view_scope(db.query(AnalysisView), current_user)
    if dataset_id:
        query = query.filter(AnalysisView.dataset_id == dataset_id)
    items = query.order_by(AnalysisView.updated_at.desc()).all()
    return {"items": items, "total": len(items)}


@router.post("", response_model=AnalysisViewOut)
def create_analysis_view(
    payload: AnalysisViewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_action(current_user, "analysis.create")
    _ensure_values(payload.chart_type, payload.status, payload.visibility)
    dataset = _get_dataset_for_user(db, payload.dataset_id, current_user)
    view = AnalysisView(
        **payload.model_dump(),
        org_id=dataset.org_id,
        owner_id=getattr(current_user, "id", None),
    )
    db.add(view)
    db.commit()
    db.refresh(view)
    try_record_audit_log(
        db,
        actor=current_user,
        action="analysis_view.create",
        resource_type="analysis_view",
        resource_id=view.id,
        resource_name=view.name,
        org_id=view.org_id,
        message="自助分析视图已创建",
        detail={"dataset_id": view.dataset_id, "chart_type": view.chart_type},
    )
    return view


@router.post("/preview-draft")
def preview_analysis_view_draft(
    payload: AnalysisDraftPreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_action(current_user, "analysis.read")
    _ensure_values(payload.chart_type)
    dataset = _get_dataset_for_user(db, payload.dataset_id, current_user)
    datasource = _get_datasource_for_user(db, dataset.datasource_id, current_user)
    return _preview_config(_analysis_config_from_payload(payload), dataset, datasource, payload.limit)


@router.get("/{view_id}", response_model=AnalysisViewOut)
def get_analysis_view(
    view_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_action(current_user, "analysis.read")
    return _get_view_for_user(db, view_id, current_user)


@router.put("/{view_id}", response_model=AnalysisViewOut)
def update_analysis_view(
    view_id: int,
    payload: AnalysisViewUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_action(current_user, "analysis.update")
    view = _get_manageable_view(db, view_id, current_user)
    updates = payload.model_dump(exclude_unset=True)
    _ensure_values(updates.get("chart_type"), updates.get("status"), updates.get("visibility"))
    if "dataset_id" in updates:
        dataset = _get_dataset_for_user(db, updates["dataset_id"], current_user)
        view.org_id = dataset.org_id
    for key, value in updates.items():
        setattr(view, key, value)
    db.commit()
    db.refresh(view)
    return view


@router.delete("/{view_id}")
def delete_analysis_view(
    view_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_action(current_user, "analysis.delete")
    view = _get_manageable_view(db, view_id, current_user)
    db.delete(view)
    db.commit()
    return {"status": "ok"}


@router.post("/{view_id}/preview")
def preview_analysis_view(
    view_id: int,
    payload: AnalysisPreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_action(current_user, "analysis.read")
    view = _get_view_for_user(db, view_id, current_user)
    dataset = _get_dataset_for_user(db, view.dataset_id, current_user)
    datasource = _get_datasource_for_user(db, dataset.datasource_id, current_user)
    return _preview_config(view, dataset, datasource, payload.limit, view.id)


@router.post("/{view_id}/copy", response_model=AnalysisViewOut)
def copy_analysis_view(
    view_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_action(current_user, "analysis.create")
    view = _get_view_for_user(db, view_id, current_user)
    copied = AnalysisView(
        name=f"{view.name} 副本",
        description=view.description,
        dataset_id=view.dataset_id,
        chart_type=view.chart_type,
        dimensions=view.dimensions or [],
        measures=view.measures or [],
        filters=view.filters or [],
        sorts=view.sorts or [],
        calculation_fields_json=view.calculation_fields_json or {},
        visual_config_json=view.visual_config_json or {},
        interaction_json=view.interaction_json or {},
        status="draft",
        visibility="private",
        org_id=view.org_id,
        owner_id=getattr(current_user, "id", None),
    )
    db.add(copied)
    db.commit()
    db.refresh(copied)
    return copied


@router.post("/{view_id}/publish", response_model=AnalysisViewOut)
def publish_analysis_view(
    view_id: int,
    payload: AnalysisPublishRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_action(current_user, "analysis.update")
    view = _get_manageable_view(db, view_id, current_user)
    _ensure_values(None, payload.status, payload.visibility)
    view.status = payload.status
    view.visibility = payload.visibility
    db.commit()
    db.refresh(view)
    try_record_audit_log(
        db,
        actor=current_user,
        action="analysis_view.publish",
        resource_type="analysis_view",
        resource_id=view.id,
        resource_name=view.name,
        org_id=view.org_id,
        message="自助分析视图发布状态已更新",
        detail={"status": view.status, "visibility": view.visibility},
    )
    return view


@router.post("/{view_id}/add-to-dashboard")
def add_analysis_view_to_dashboard(
    view_id: int,
    payload: AnalysisDashboardAttachRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_action(current_user, "analysis.read")
    view = _get_view_for_user(db, view_id, current_user)
    dashboard = db.query(Dashboard).filter(Dashboard.id == payload.dashboard_id).first()
    if not dashboard:
        raise HTTPException(status_code=404, detail="看板不存在")
    if not _can_manage_dashboard(current_user, dashboard):
        raise HTTPException(status_code=403, detail="无权修改此看板")

    dataset = _get_dataset_for_user(db, view.dataset_id, current_user)
    datasource = _get_datasource_for_user(db, dataset.datasource_id, current_user)
    query_plan = _build_query_plan(view, dataset, datasource, 5000)
    max_order = db.query(PinnedChart).filter(PinnedChart.user_id == current_user.id).count()
    chart = PinnedChart(
        user_id=current_user.id,
        datasource_id=datasource.id,
        title=view.name,
        description=view.description,
        sql_query=_render_sql_with_params(query_plan["sql"], query_plan["params"]),
        chart_type=view.chart_type,
        sort_order="desc",
        display_order=max_order,
    )
    db.add(chart)
    db.flush()
    component_id = _append_analysis_chart_to_dashboard(dashboard, chart, view, payload)
    db.commit()
    db.refresh(chart)
    return {
        "dashboard_id": dashboard.id,
        "component_id": component_id,
        "chart": {
            "id": chart.id,
            "title": chart.title,
            "description": chart.description,
            "sql_query": chart.sql_query,
            "chart_type": chart.chart_type,
            "sort_order": chart.sort_order,
            "display_order": chart.display_order,
            "datasource_id": chart.datasource_id,
        },
    }
