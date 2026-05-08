import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text

from app.core.excel_executor import execute_excel_query
from app.db.session import get_datasource_engine


SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SAFE_FIELD_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?$")
FILTER_RE = re.compile(
    r"^\s*(?P<field>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?)\s*"
    r"(?P<op>IS\s+NOT\s+NULL|IS\s+NULL|>=|<=|!=|=|>|<|LIKE)\s*"
    r"(?P<value>.*?)\s*$",
    re.IGNORECASE,
)
AGGREGATION_RE = re.compile(
    r"^\s*(?P<fn>SUM|AVG|COUNT|MIN|MAX)\s*\(\s*"
    r"(?P<field>\*|[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?)\s*\)\s*$",
    re.IGNORECASE,
)
AGGREGATIONS = {
    "sum": "SUM",
    "avg": "AVG",
    "count": "COUNT",
    "min": "MIN",
    "max": "MAX",
    "count_distinct": "COUNT DISTINCT",
}


@dataclass
class SemanticSqlPlan:
    sql: str
    params: dict[str, Any]
    columns: list[str]
    labels: dict[str, str]


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _assert_identifier(value: Any, label: str) -> str:
    clean = _clean_text(value)
    if not SAFE_IDENTIFIER_RE.match(clean):
        raise ValueError(f"{label}不合法")
    return clean


def _assert_field(value: Any, label: str, allow_star: bool = False) -> str:
    clean = _clean_text(value)
    if allow_star and clean == "*":
        return clean
    if not SAFE_FIELD_RE.match(clean):
        raise ValueError(f"{label}不合法")
    return clean


def _source_table(dataset: Any) -> str:
    fields_json = dataset.fields_json if isinstance(dataset.fields_json, dict) else {}
    table = _clean_text(fields_json.get("table"))
    if not table:
        for field in _as_list(fields_json.get("fields")):
            name = _field_name(field)
            if "." in name:
                table = name.split(".", 1)[0]
                break
    return _assert_identifier(table, "数据集主表")


def _field_name(field: Any) -> str:
    """Extract field name from either a string or a dict with a 'name' key."""
    if isinstance(field, dict):
        return _clean_text(field.get("name"))
    return _clean_text(field)


def _infer_table(dataset: Any) -> str:
    fields_json = dataset.fields_json if isinstance(dataset.fields_json, dict) else {}
    table = _clean_text(fields_json.get("table"))
    if table:
        return table
    for field in _as_list(fields_json.get("fields")):
        name = _field_name(field)
        if "." in name:
            return name.split(".", 1)[0]
    return ""


def _split_field(field: str, default_table: str) -> tuple[str, str]:
    clean = _clean_text(field)
    if "." in clean:
        table, column = clean.split(".", 1)
    else:
        table, column = default_table, clean
    return _assert_identifier(table, "表名"), _assert_identifier(column, "字段名")


def _column_ref(field: str, default_table: str) -> str:
    table, column = _split_field(field, default_table)
    return f"{table}.{column}"


def _column_name(field: str, default_table: str) -> str:
    return _split_field(field, default_table)[1]


def _field_column_name(field: str) -> str:
    clean = _assert_field(field, "字段")
    return clean.split(".", 1)[1] if "." in clean else clean


def _normalize_metric(raw: dict[str, Any], seen_ids: set[str]) -> dict[str, Any]:
    item_id = _assert_identifier(raw.get("id"), "指标ID")
    if item_id in seen_ids:
        raise ValueError(f"语义ID重复: {item_id}")
    seen_ids.add(item_id)
    aggregation = _clean_text(raw.get("aggregation") or "sum").lower()
    if aggregation not in AGGREGATIONS:
        raise ValueError(f"指标聚合方式不支持: {aggregation}")
    field = _assert_field(raw.get("field"), "指标字段", allow_star=aggregation == "count")
    item = {
        "id": item_id,
        "field": field,
        "label": _clean_text(raw.get("label")) or item_id,
        "aggregation": aggregation,
    }
    if raw.get("description"):
        item["description"] = _clean_text(raw.get("description"))
    if raw.get("format"):
        item["format"] = _clean_text(raw.get("format"))
    return item


def _normalize_dimension(raw: dict[str, Any], seen_ids: set[str], section: str) -> dict[str, Any]:
    item_id = _assert_identifier(raw.get("id"), "维度ID")
    if item_id in seen_ids:
        raise ValueError(f"语义ID重复: {item_id}")
    seen_ids.add(item_id)
    item = {
        "id": item_id,
        "field": _assert_field(raw.get("field"), "维度字段"),
        "label": _clean_text(raw.get("label")) or item_id,
    }
    if section == "time_dimensions":
        item["granularity"] = _clean_text(raw.get("granularity") or "day")
    if raw.get("description"):
        item["description"] = _clean_text(raw.get("description"))
    return item


def normalize_semantic_model(model: Any, dataset: Any | None = None) -> dict[str, Any]:
    del dataset
    if not isinstance(model, dict):
        raise ValueError("语义模型必须是 JSON 对象")

    seen_ids: set[str] = set()
    normalized: dict[str, Any] = {
        "dimensions": [],
        "metrics": [],
        "time_dimensions": [],
        "synonyms": [],
    }
    for section in ("dimensions", "time_dimensions"):
        for raw in _as_list(model.get(section)):
            if not isinstance(raw, dict):
                raise ValueError(f"{section} 中存在不合法项")
            normalized[section].append(_normalize_dimension(raw, seen_ids, section))

    for raw in _as_list(model.get("metrics")):
        if not isinstance(raw, dict):
            raise ValueError("metrics 中存在不合法项")
        normalized["metrics"].append(_normalize_metric(raw, seen_ids))

    for raw in _as_list(model.get("synonyms")):
        if not isinstance(raw, dict):
            raise ValueError("synonyms 中存在不合法项")
        term = _clean_text(raw.get("term"))
        target_id = _clean_text(raw.get("target_id"))
        if not term:
            raise ValueError("同义词不能为空")
        if target_id and target_id not in seen_ids:
            raise ValueError(f"同义词目标不存在: {target_id}")
        normalized["synonyms"].append({"term": term, "target_id": target_id})
    return normalized


def _unique_id(candidate: str, seen: set[str]) -> str:
    clean = re.sub(r"[^A-Za-z0-9_]", "_", candidate).strip("_") or "field"
    if not re.match(r"^[A-Za-z_]", clean):
        clean = f"f_{clean}"
    value = clean
    index = 2
    while value in seen:
        value = f"{clean}_{index}"
        index += 1
    seen.add(value)
    return value


def infer_semantic_model(dataset: Any) -> dict[str, Any]:
    if isinstance(getattr(dataset, "semantic_model_json", None), dict):
        return normalize_semantic_model(dataset.semantic_model_json, dataset)

    table = _infer_table(dataset)
    fields_json = dataset.fields_json if isinstance(dataset.fields_json, dict) else {}
    aggregations_json = dataset.aggregations_json if isinstance(dataset.aggregations_json, dict) else {}
    seen: set[str] = set()
    dimensions: list[dict[str, Any]] = []
    metrics: list[dict[str, Any]] = []

    for field in _as_list(fields_json.get("fields")):
        clean = _field_name(field)
        if not clean or clean.endswith(".*"):
            continue
        label = _clean_text(field.get("label") if isinstance(field, dict) else clean) or clean
        column = _column_name(clean, table) if table else _field_column_name(clean)
        item_id = _unique_id(column, seen)
        dimensions.append({"id": item_id, "field": _assert_field(clean, "字段"), "label": label})

    for expression in _as_list(aggregations_json.get("aggregations")):
        match = AGGREGATION_RE.match(_clean_text(expression))
        if not match:
            continue
        fn = match.group("fn").lower()
        field = match.group("field")
        column = "all" if field == "*" else (_column_name(field, table) if table else _field_column_name(field))
        item_id = _unique_id(f"{fn}_{column}", seen)
        metrics.append(
            {
                "id": item_id,
                "field": _assert_field(field, "指标字段", allow_star=fn == "count"),
                "label": item_id,
                "aggregation": fn,
            }
        )

    return normalize_semantic_model(
        {
            "dimensions": dimensions,
            "metrics": metrics,
            "time_dimensions": [],
            "synonyms": [],
        },
        dataset,
    )


def _payload_list(payload: Any, key: str) -> list[Any]:
    if isinstance(payload, dict):
        return _as_list(payload.get(key))
    return _as_list(getattr(payload, key, None))


def _payload_int(payload: Any, key: str, default: int) -> int:
    if isinstance(payload, dict):
        value = payload.get(key, default)
    else:
        value = getattr(payload, key, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_filter_value(value: str) -> str:
    clean = value.strip()
    if len(clean) >= 2 and clean[0] == clean[-1] and clean[0] in {"'", '"'}:
        return clean[1:-1]
    return clean


def _semantic_targets(model: dict[str, Any]) -> dict[str, dict[str, Any]]:
    targets: dict[str, dict[str, Any]] = {}
    for item in model["dimensions"] + model["time_dimensions"] + model["metrics"]:
        targets[item["id"]] = item
    return targets


def _render_filter(
    item: Any,
    default_table: str,
    params: dict[str, Any],
    index: int,
    targets: dict[str, dict[str, Any]] | None = None,
) -> str:
    if isinstance(item, dict):
        raw_field = _clean_text(item.get("id") or item.get("field") or item.get("column"))
        field = targets.get(raw_field, {}).get("field", raw_field) if targets else raw_field
        operator = _clean_text(item.get("operator") or item.get("op") or "=").upper()
        value = item.get("value")
    else:
        match = FILTER_RE.match(str(item))
        if not match:
            raise ValueError(f"筛选条件不合法: {item}")
        field = match.group("field")
        operator = re.sub(r"\s+", " ", match.group("op").upper())
        value = _normalize_filter_value(match.group("value"))

    operator = re.sub(r"\s+", " ", operator)
    if operator not in {"=", "!=", ">", ">=", "<", "<=", "LIKE", "IS NULL", "IS NOT NULL"}:
        raise ValueError(f"筛选操作符不支持: {operator}")
    column_ref = _column_ref(_assert_field(field, "筛选字段"), default_table)
    if operator in {"IS NULL", "IS NOT NULL"}:
        return f"{column_ref} {operator}"

    param_name = f"semantic_filter_{index}"
    if operator == "LIKE":
        text_value = str(value)
        params[param_name] = text_value if "%" in text_value else f"%{text_value}%"
    else:
        params[param_name] = value
    return f"{column_ref} {operator} :{param_name}"


def _render_metric(metric: dict[str, Any], default_table: str) -> str:
    aggregation = metric["aggregation"]
    alias = _assert_identifier(metric["id"], "指标ID")
    if aggregation == "count" and metric["field"] == "*":
        return f"COUNT(*) AS {alias}"
    field = _column_ref(metric["field"], default_table)
    if aggregation == "count_distinct":
        return f"COUNT(DISTINCT {field}) AS {alias}"
    return f"{AGGREGATIONS[aggregation]}({field}) AS {alias}"


def build_semantic_query_plan(dataset: Any, payload: Any) -> SemanticSqlPlan:
    table = _source_table(dataset)
    model = infer_semantic_model(dataset)
    targets = _semantic_targets(model)
    dimensions_by_id = {item["id"]: item for item in model["dimensions"] + model["time_dimensions"]}
    metrics_by_id = {item["id"]: item for item in model["metrics"]}

    requested_dimensions = [_assert_identifier(item, "维度ID") for item in _payload_list(payload, "dimensions")]
    requested_metrics = [_assert_identifier(item, "指标ID") for item in _payload_list(payload, "metrics")]
    if not requested_dimensions and not requested_metrics:
        raise ValueError("请至少选择一个维度或指标")

    missing_dimensions = [item for item in requested_dimensions if item not in dimensions_by_id]
    missing_metrics = [item for item in requested_metrics if item not in metrics_by_id]
    if missing_dimensions:
        raise ValueError(f"维度不存在: {', '.join(missing_dimensions)}")
    if missing_metrics:
        raise ValueError(f"指标不存在: {', '.join(missing_metrics)}")

    dimension_defs = [dimensions_by_id[item] for item in requested_dimensions]
    metric_defs = [metrics_by_id[item] for item in requested_metrics]
    select_parts: list[str] = []
    group_by_parts: list[str] = []
    order_by_parts: list[str] = []
    columns: list[str] = []
    labels: dict[str, str] = {}

    for dimension in dimension_defs:
        alias = _assert_identifier(dimension["id"], "维度ID")
        column_ref = _column_ref(dimension["field"], table)
        select_parts.append(f"{column_ref} AS {alias}")
        group_by_parts.append(column_ref)
        order_by_parts.append(alias)
        columns.append(alias)
        labels[alias] = dimension["label"]

    for metric in metric_defs:
        alias = _assert_identifier(metric["id"], "指标ID")
        select_parts.append(_render_metric(metric, table))
        columns.append(alias)
        labels[alias] = metric["label"]

    params: dict[str, Any] = {}
    dataset_filters = []
    filters_json = dataset.filters_json if isinstance(dataset.filters_json, dict) else {}
    for index, item in enumerate(_as_list(filters_json.get("filters"))):
        dataset_filters.append(_render_filter(item, table, params, index))

    request_filters = []
    offset = len(dataset_filters)
    for index, item in enumerate(_payload_list(payload, "filters"), start=offset):
        request_filters.append(_render_filter(item, table, params, index, targets))

    limit = max(1, min(_payload_int(payload, "limit", 100), 5000))
    params["limit"] = limit

    sql_parts = [
        f"{'SELECT DISTINCT' if dimension_defs and not metric_defs else 'SELECT'} {', '.join(select_parts)}",
        f"FROM {table}",
    ]
    where_parts = dataset_filters + request_filters
    if where_parts:
        sql_parts.append(f"WHERE {' AND '.join(where_parts)}")
    if group_by_parts and metric_defs:
        sql_parts.append(f"GROUP BY {', '.join(group_by_parts)}")
    if order_by_parts:
        sql_parts.append(f"ORDER BY {', '.join(order_by_parts)}")
    sql_parts.append("LIMIT :limit")

    return SemanticSqlPlan(
        sql="\n".join(sql_parts),
        params=params,
        columns=columns,
        labels=labels,
    )


def _sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    return f"'{str(value).replace(chr(39), chr(39) * 2)}'"


def render_sql_with_params(sql: str, params: dict[str, Any]) -> str:
    rendered = sql
    for key in sorted(params, key=len, reverse=True):
        rendered = rendered.replace(f":{key}", _sql_literal(params[key]))
    return rendered


def execute_semantic_sql(datasource: Any, sql: str, params: dict[str, Any]) -> dict[str, Any]:
    if datasource.source_type == "excel":
        return execute_excel_query(datasource.database_url, render_sql_with_params(sql, params))

    engine = get_datasource_engine(datasource.database_url)
    with engine.connect() as conn:
        result = conn.execute(text(sql), params)
        columns = list(result.keys())
        rows = [dict(row._mapping) for row in result.fetchall()]
    return {"columns": columns, "rows": rows}
