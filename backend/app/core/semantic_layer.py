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
    r"^\s*(?P<fn>SUM|AVG|COUNT|COUNT_DISTINCT|MIN|MAX)\s*\(\s*"
    r"(?:(?P<distinct>DISTINCT)\s+)?"
    r"(?P<field>\*|[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?)\s*\)\s*$",
    re.IGNORECASE,
)
AGGREGATIONS = {
    "sum": "SUM",
    "avg": "AVG",
    "count": "COUNT",
    "min": "MIN",
    "max": "MAX",
    "count_distinct": "COUNT",
}

# 时间字段启发词（参考 app/core/dataset_ai_config.py 的 TIME_HINTS，保持口径一致）
TIME_HINTS = ("time", "date", "datetime", "dt", "day", "month", "year", "ymd")
_TIME_HINT_CN = ("日期", "时间", "年月", "年度", "年份", "月份")

# 时间粒度 -> 各方言的时间表达式模板。year/month 输出文本便于展示（YYYY / YYYY-MM）；
# sqlite: strftime(format, col)；duckdb: strftime(col, format)（参数顺序与 sqlite 相反）；
# mysql/doris: DATE_FORMAT(col, format)；postgresql: to_char(col, format)。
_TIME_EXPRESSIONS = {
    "sqlite": {
        "year": "strftime('%Y', {col})",
        "month": "strftime('%Y-%m', {col})",
    },
    "duckdb": {
        "year": "strftime({col}, '%Y')",
        "month": "strftime({col}, '%Y-%m')",
    },
    "mysql": {
        "year": "DATE_FORMAT({col}, '%Y')",
        "month": "DATE_FORMAT({col}, '%Y-%m')",
    },
    "postgresql": {
        "year": "to_char({col}, 'YYYY')",
        "month": "to_char({col}, 'YYYY-MM')",
    },
}
TIME_GRANULARITY_SUFFIX = (("year", "_year", "年份"), ("month", "_month", "月份"))

JOIN_CLAUSE_RE = re.compile(
    r"^\s*(?P<type>(?:(?:LEFT|RIGHT|INNER|FULL|CROSS)\s+(?:OUTER\s+)?)?JOIN)\s+(?P<body>.+?)\s*$",
    re.IGNORECASE,
)
JOIN_ON_PREFIX_RE = re.compile(r"^ON\s+(?P<body>.+?)\s*$", re.IGNORECASE)
JOIN_FIELD_TOKEN = r"(?:[A-Za-z_][A-Za-z0-9_]*\.)?[A-Za-z_][A-Za-z0-9_]*"
JOIN_CONDITION_RE = re.compile(
    rf"^(?P<left>{JOIN_FIELD_TOKEN})\s*(?P<op>=|!=|>|>=|<|<=)\s*(?P<right>{JOIN_FIELD_TOKEN})$",
    re.IGNORECASE,
)
QUALIFIED_COLUMN_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\b")


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
        for field in _as_list(fields_json.get("dimensions")) or _as_list(fields_json.get("fields")):
            name = _field_name(field)
            if "." in name:
                table = name.split(".", 1)[0]
                break
    return _assert_identifier(table, "数据集主表")


def _field_name(field: Any) -> str:
    """Extract field name from either a string or a dict with a 'name' key."""
    if isinstance(field, dict):
        return _clean_text(field.get("field") or field.get("name") or field.get("key"))
    return _clean_text(field)


def _field_label(field: Any, fallback: str) -> str:
    if isinstance(field, dict):
        return _clean_text(field.get("alias") or field.get("label") or field.get("display_name")) or fallback
    return fallback


def _infer_table(dataset: Any) -> str:
    fields_json = dataset.fields_json if isinstance(dataset.fields_json, dict) else {}
    table = _clean_text(fields_json.get("table"))
    if table:
        return table
    for field in _as_list(fields_json.get("dimensions")) or _as_list(fields_json.get("fields")):
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


def _is_time_column(column: str) -> bool:
    """按字段名启发式判断是否为时间字段（与 dataset_ai_config 的口径保持一致）。"""
    lowered = column.lower()
    return any(hint in lowered for hint in TIME_HINTS)


def _is_time_label(label: str) -> bool:
    return any(token in label for token in _TIME_HINT_CN)


def _time_expression(dialect: str, column_ref: str, granularity: str) -> str:
    """生成方言感知的时间聚合表达式；未知方言/粒度回退为原列，保证 SQL 合法。"""
    template = _TIME_EXPRESSIONS.get(dialect or "", {}).get(granularity)
    if not template:
        return column_ref
    return template.format(col=column_ref)


def _dialect_name(datasource: Any) -> str:
    """根据数据源推断 SQL 方言；无法识别时返回空串（时间聚合回退原列）。"""
    if datasource is None:
        return ""
    if getattr(datasource, "source_type", None) == "excel":
        return "duckdb"
    url = str(getattr(datasource, "database_url", "") or "").lower()
    if not url:
        return ""
    if "mariadb" in url or "doris" in url or "mysql" in url:
        return "mysql"
    if "postgres" in url:
        return "postgresql"
    if url.startswith("sqlite") or "sqlite" in url:
        return "sqlite"
    if "duckdb" in url:
        return "duckdb"
    try:
        engine = get_datasource_engine(str(getattr(datasource, "database_url", "")))
        return engine.dialect.name if engine.dialect.name in _TIME_EXPRESSIONS else ""
    except Exception:
        return ""


def expand_time_dimensions(model: dict[str, Any]) -> dict[str, Any]:
    """在规范化语义模型之上幂等展开派生时间维度（day/year/month）。

    仅在读取/查询构建出口使用、不落库；目标 ID 已存在时自动跳过，可安全重复调用。
    """
    normalized = normalize_semantic_model(model)
    existing_ids = {
        item["id"]
        for item in normalized["dimensions"] + normalized["metrics"] + normalized["time_dimensions"]
    }
    expanded: list[dict[str, Any]] = []
    for item in normalized["time_dimensions"]:
        expanded.append(item)
        for granularity, suffix, tail in TIME_GRANULARITY_SUFFIX:
            derived_id = f"{item['id']}{suffix}"
            if derived_id in existing_ids:
                continue
            label = item.get("label") or item["id"]
            derived = dict(item)
            derived.update(id=derived_id, granularity=granularity, label=f"{label}（{tail}）")
            expanded.append(derived)
            existing_ids.add(derived_id)
    normalized["time_dimensions"] = expanded
    return normalized


def infer_semantic_model(dataset: Any) -> dict[str, Any]:
    """推断（或直接读取）数据集的语义模型，并展开时间粒度为 day/year/month。

    本函数只用于读取/查询路径，其结果不用于持久化，存储仍保留用户编辑的原始语义模型。
    """
    if isinstance(getattr(dataset, "semantic_model_json", None), dict):
        return expand_time_dimensions(normalize_semantic_model(dataset.semantic_model_json, dataset))

    table = _infer_table(dataset)
    fields_json = dataset.fields_json if isinstance(dataset.fields_json, dict) else {}
    aggregations_json = dataset.aggregations_json if isinstance(dataset.aggregations_json, dict) else {}
    seen: set[str] = set()
    dimensions: list[dict[str, Any]] = []
    time_dimensions: list[dict[str, Any]] = []
    metrics: list[dict[str, Any]] = []

    dimension_fields = _as_list(fields_json.get("dimensions")) or _as_list(fields_json.get("fields"))
    for field in dimension_fields:
        clean = _field_name(field)
        if not clean or clean.endswith(".*"):
            continue
        label = _field_label(field, clean)
        column = _column_name(clean, table) if table else _field_column_name(clean)
        item_id = _unique_id(column, seen)
        # 名称/别名命中时间启发词的字段归入时间维度（granularity day），
        # 使查询构建时可展开为 _year/_month 派生粒度进行年/月聚合
        if _is_time_column(column) or _is_time_label(label):
            time_dimensions.append(
                {
                    "id": item_id,
                    "field": _assert_field(clean, "字段"),
                    "label": label,
                    "granularity": "day",
                }
            )
        else:
            dimensions.append({"id": item_id, "field": _assert_field(clean, "字段"), "label": label})

    metric_expressions = _as_list(fields_json.get("metrics")) or _as_list(aggregations_json.get("aggregations"))
    for expression in metric_expressions:
        metric_alias = None
        if isinstance(expression, dict):
            metric_alias = _field_label(expression, "")
            raw_expression = _clean_text(expression.get("expression"))
            if not raw_expression:
                metric_field = _field_name(expression)
                metric_fn = _clean_text(expression.get("aggregation") or expression.get("fn") or "SUM").upper()
                raw_expression = f"{metric_fn}({metric_field})" if metric_field and metric_fn else ""
        else:
            raw_expression = _clean_text(expression)
        match = AGGREGATION_RE.match(raw_expression)
        if not match:
            continue
        fn = "count_distinct" if match.group("fn").lower() == "count_distinct" or match.group("distinct") else match.group("fn").lower()
        field = match.group("field")
        column = "all" if field == "*" else (_column_name(field, table) if table else _field_column_name(field))
        item_id = _unique_id(f"{fn}_{column}", seen)
        metrics.append(
            {
                "id": item_id,
                "field": _assert_field(field, "指标字段", allow_star=fn == "count"),
                "label": metric_alias or item_id,
                "aggregation": fn,
            }
        )

    return expand_time_dimensions(
        normalize_semantic_model(
            {
                "dimensions": dimensions,
                "metrics": metrics,
                "time_dimensions": time_dimensions,
                "synonyms": [],
            },
            dataset,
        )
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


def _normalize_join_type(value: Any) -> str:
    raw = re.sub(r"\s+", " ", _clean_text(value).upper())
    if raw not in {
        "JOIN",
        "INNER JOIN",
        "LEFT JOIN",
        "LEFT OUTER JOIN",
        "RIGHT JOIN",
        "RIGHT OUTER JOIN",
        "FULL JOIN",
        "FULL OUTER JOIN",
        "CROSS JOIN",
    }:
        raise ValueError(f"Join 类型不合法: {raw or '(空)'}")
    return raw


def _qualify_join_field(field: str, default_table: str) -> str:
    clean = _assert_field(field, "Join 关联字段")
    if "." not in clean:
        return f"{default_table}.{clean}"
    return clean


def _join_condition_parts(condition: str, default_table: str) -> tuple[str, str, str]:
    match = JOIN_CONDITION_RE.match(condition.strip())
    if not match:
        raise ValueError(f"Join 关联条件不合法: {condition}")
    left = _qualify_join_field(match.group("left"), default_table)
    right = _qualify_join_field(match.group("right"), default_table)
    return left, match.group("op").strip(), right


def _join_clause_parts(dataset: Any, default_table: str) -> tuple[list[str], list[str]]:
    """从数据集 joins_json 渲染 JOIN 子句（兼容 left/right、right+on、字符串三种存储格式）。

    返回 (JOIN 子句列表, FROM+JOIN 引入的表名列表)，引用顺序错误的关联会给出明确报错。
    """
    joins_json = dataset.joins_json if isinstance(getattr(dataset, "joins_json", None), dict) else {}
    known_tables: list[str] = [default_table]
    known_set: set[str] = {default_table}
    clauses: list[str] = []
    for item in _as_list(joins_json.get("joins")):
        declared_table = ""
        if isinstance(item, dict):
            join_type = _normalize_join_type(item.get("type") or item.get("join_type") or "LEFT JOIN")
            raw_left = _clean_text(item.get("left"))
            raw_right = _clean_text(item.get("right"))
            raw_on = _clean_text(item.get("on") or item.get("join_on"))
            if raw_on:
                condition = raw_on
            elif raw_left and raw_right:
                condition = f"{raw_left} {_clean_text(item.get('op') or '=')} {raw_right}"
            else:
                raise ValueError("Join 配置缺少关联条件（需要 on 或 left/right 字段）")
            declared_table = _clean_text(item.get("table"))
        else:
            match = JOIN_CLAUSE_RE.match(_clean_text(item))
            if not match:
                raise ValueError(f"Join 关系不合法: {item}")
            join_type = _normalize_join_type(match.group("type"))
            body = match.group("body").strip()
            table_match = re.match(
                rf"^(?P<table>[A-Za-z_][A-Za-z0-9_]*)\s+ON\s+(?P<cond>.+)$",
                body,
                re.IGNORECASE,
            )
            if table_match:
                declared_table = table_match.group("table")
                condition = table_match.group("cond")
            else:
                condition = body
        if declared_table:
            declared_table = _assert_identifier(declared_table, "Join 表名")
        left_field, op, right_field = _join_condition_parts(condition, default_table)
        left_table, right_table = left_field.split(".", 1)[0], right_field.split(".", 1)[0]
        if declared_table:
            target_table = declared_table
        elif right_table not in known_set:
            target_table = right_table
        else:
            target_table = left_table
        if target_table not in {left_table, right_table}:
            raise ValueError(f"Join 表 {target_table} 未出现在关联条件 {left_field} {op} {right_field} 中")
        if target_table in known_set:
            raise ValueError(f"Join 目标表重复或已作为主表: {target_table}")
        other_table = right_table if target_table == left_table else left_table
        if other_table not in known_set:
            raise ValueError(
                f"Join 关联表 {other_table} 尚未引入（数据集主表或更早的 JOIN 必须先出现），"
                f"请检查数据集关联配置顺序"
            )
        known_tables.append(target_table)
        known_set.add(target_table)
        clauses.append(f"{join_type} {target_table} ON {left_field} {op} {right_field}")
    return clauses, known_tables


def _match_requested(requested_ids: list[str], defs: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """按 ID 精确匹配，失败时做大小写不敏感回退，返回 (命中的定义, 缺失 ID 列表)。"""
    by_exact = {item["id"]: item for item in defs}
    by_lower: dict[str, dict[str, Any]] = {}
    for item in defs:
        by_lower.setdefault(item["id"].lower(), item)
    matched: list[dict[str, Any]] = []
    missing: list[str] = []
    for requested in requested_ids:
        if requested in by_exact:
            matched.append(by_exact[requested])
        elif requested.lower() in by_lower:
            matched.append(by_lower[requested.lower()])
        else:
            missing.append(requested)
    return matched, missing


def _available_id_hint(defs: list[dict[str, Any]]) -> str:
    ids = [item["id"] for item in defs]
    preview = ", ".join(ids[:30])
    if len(ids) > 30:
        preview += ", ..."
    return preview or "无"


def build_semantic_query_plan(dataset: Any, payload: Any, datasource: Any | None = None) -> SemanticSqlPlan:
    table = _source_table(dataset)
    dialect = _dialect_name(datasource)
    model = infer_semantic_model(dataset)
    targets = _semantic_targets(model)
    dimension_defs_all = model["dimensions"] + model["time_dimensions"]
    metric_defs_all = model["metrics"]
    time_dimension_ids = {item["id"] for item in model["time_dimensions"]}

    requested_dimensions = [_assert_identifier(item, "维度ID") for item in _payload_list(payload, "dimensions")]
    requested_metrics = [_assert_identifier(item, "指标ID") for item in _payload_list(payload, "metrics")]
    if not requested_dimensions and not requested_metrics:
        raise ValueError("请至少选择一个维度或指标")

    dimension_defs, missing_dimensions = _match_requested(requested_dimensions, dimension_defs_all)
    metric_defs, missing_metrics = _match_requested(requested_metrics, metric_defs_all)
    if missing_dimensions:
        raise ValueError(
            f"维度不存在: {', '.join(missing_dimensions)}。"
            f"可用维度/时间维度: {_available_id_hint(dimension_defs_all)}"
        )
    if missing_metrics:
        raise ValueError(f"指标不存在: {', '.join(missing_metrics)}。可用指标: {_available_id_hint(metric_defs_all)}")

    join_clauses, joined_tables = _join_clause_parts(dataset, table)

    select_parts: list[str] = []
    group_by_parts: list[str] = []
    order_by_parts: list[str] = []
    columns: list[str] = []
    labels: dict[str, str] = {}

    for dimension in dimension_defs:
        alias = _assert_identifier(dimension["id"], "维度ID")
        column_ref = _column_ref(dimension["field"], table)
        if dimension["id"] in time_dimension_ids and dimension.get("granularity") in {"year", "month"}:
            # 按年/月聚合：SELECT 与 GROUP BY 都使用方言时间表达式
            column_ref = _time_expression(dialect, column_ref, dimension["granularity"])
        select_parts.append(f"{column_ref} AS {alias}")
        group_by_parts.append(column_ref)
        order_by_parts.append(alias)
        columns.append(alias)
        labels[alias] = dimension["label"]

    metric_aliases: list[str] = []
    for metric in metric_defs:
        alias = _assert_identifier(metric["id"], "指标ID")
        select_parts.append(_render_metric(metric, table))
        columns.append(alias)
        labels[alias] = metric["label"]
        metric_aliases.append(alias)

    if metric_aliases:
        order_by_parts = [f"{metric_aliases[0]} DESC", *order_by_parts]

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

    where_parts = dataset_filters + request_filters
    sql_parts = [
        f"{'SELECT DISTINCT' if dimension_defs and not metric_defs else 'SELECT'} {', '.join(select_parts)}",
        f"FROM {table}",
        *join_clauses,
    ]
    if where_parts:
        sql_parts.append(f"WHERE {' AND '.join(where_parts)}")
    if group_by_parts and metric_defs:
        sql_parts.append(f"GROUP BY {', '.join(group_by_parts)}")
    if order_by_parts:
        sql_parts.append(f"ORDER BY {', '.join(order_by_parts)}")
    sql_parts.append("LIMIT :limit")

    # 跨表引用校验：SELECT/WHERE/GROUP BY 中出现的限定表必须位于 FROM+JOIN 集合内
    allowed_tables = set(joined_tables)
    rendered_body = "\n".join(select_parts + group_by_parts + where_parts + join_clauses)
    referenced_tables = {match.group(1) for match in QUALIFIED_COLUMN_RE.finditer(rendered_body)} - allowed_tables
    if referenced_tables:
        raise ValueError(
            "字段引用了未关联的表: "
            + ", ".join(sorted(referenced_tables))
            + f"。数据集主表/已关联表: {', '.join(joined_tables)}；"
            "请在数据集的“关联”中配置相应 JOIN 后重试"
        )

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
