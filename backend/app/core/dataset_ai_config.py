import json
import re
from types import SimpleNamespace
from typing import Any

from app.core.drill_config import normalize_drill_config
from app.core.llm import chat_completion
from app.core.semantic_layer import infer_semantic_model, normalize_semantic_model


NUMERIC_TYPES = {"INTEGER", "INT", "BIGINT", "FLOAT", "DOUBLE", "REAL", "NUMERIC", "DECIMAL"}
TIME_HINTS = ("time", "date", "datetime", "dt", "day", "month", "year")
METRIC_HINTS = (
    "count",
    "total",
    "sum",
    "amount",
    "qty",
    "num",
    "times",
    "duration",
    "rate",
    "oee",
    "yield",
)
DIMENSION_HINTS = (
    "id",
    "code",
    "name",
    "type",
    "status",
    "site",
    "line",
    "shift",
    "step",
    "product",
    "equipment",
    "alarm",
    "error",
    "reason",
)


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _safe_id(value: str, seen: set[str]) -> str:
    clean = re.sub(r"[^A-Za-z0-9_]", "_", value.lower()).strip("_") or "field"
    if not re.match(r"^[A-Za-z_]", clean):
        clean = f"f_{clean}"
    candidate = clean
    index = 2
    while candidate in seen:
        candidate = f"{clean}_{index}"
        index += 1
    seen.add(candidate)
    return candidate


def _column_name(field: str) -> str:
    return field.split(".", 1)[1] if "." in field else field


def _table_name(field: str, default_table: str) -> str:
    return field.split(".", 1)[0] if "." in field else default_table


def _field_name(item: Any) -> str:
    if isinstance(item, dict):
        return _clean(item.get("field") or item.get("name") or item.get("key"))
    return _clean(item)


def _field_label(item: Any, fallback: str) -> str:
    if isinstance(item, dict):
        return _clean(item.get("alias") or item.get("label") or item.get("display_name")) or fallback
    return fallback


def _schema_dict(datasource: Any) -> dict[str, Any]:
    raw = getattr(datasource, "schema_metadata", None)
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return {}


def _columns_for_table(datasource: Any, table: str | None) -> list[dict[str, Any]]:
    schema = _schema_dict(datasource)
    tables = _as_list(schema.get("tables"))
    if not table and tables:
        table = _clean(tables[0].get("name"))
    for item in tables:
        if _clean(item.get("name")) == table:
            return _as_list(item.get("columns"))
    return []


def _is_numeric(column_type: str) -> bool:
    upper = column_type.upper()
    return any(item in upper for item in NUMERIC_TYPES)


def _is_time(column_name: str, column_type: str) -> bool:
    lowered = column_name.lower()
    return any(hint in lowered for hint in TIME_HINTS) or any(hint.upper() in column_type.upper() for hint in ("DATE", "TIME"))


def _is_metric(column_name: str, column_type: str) -> bool:
    lowered = column_name.lower()
    return _is_numeric(column_type) and any(hint in lowered for hint in METRIC_HINTS)


def _is_dimension(column_name: str, column_type: str) -> bool:
    lowered = column_name.lower()
    if _is_time(column_name, column_type):
        return False
    if not _is_numeric(column_type):
        return True
    return any(hint in lowered for hint in DIMENSION_HINTS)


def _kind_for_dimension(column_name: str, is_time: bool = False) -> str:
    lowered = column_name.lower()
    if is_time:
        return "time"
    if "equipment" in lowered or "equip" in lowered:
        return "equipment"
    if "alarm" in lowered or "error" in lowered:
        return "alarm"
    if "site" in lowered:
        return "site"
    if "line" in lowered:
        return "line"
    if "shift" in lowered:
        return "shift"
    if "step" in lowered or "process" in lowered:
        return "process"
    if "product" in lowered or "sku" in lowered or "part" in lowered:
        return "product"
    if lowered.endswith("id") or "code" in lowered:
        return "code"
    return "category"


def _aggregation_for_column(column_name: str) -> str:
    lowered = column_name.lower()
    if "rate" in lowered or "oee" in lowered or "yield" in lowered:
        return "avg"
    return "sum"


def _semantic_from_schema(datasource: Any, table: str) -> dict[str, Any]:
    columns = _columns_for_table(datasource, table)
    seen: set[str] = set()
    dimensions: list[dict[str, Any]] = []
    time_dimensions: list[dict[str, Any]] = []
    metrics: list[dict[str, Any]] = []
    for column in columns:
        name = _clean(column.get("name"))
        if not name:
            continue
        column_type = _clean(column.get("type"))
        label = _clean(column.get("description")) or name
        field = f"{table}.{name}" if table else name
        if _is_time(name, column_type):
            time_dimensions.append(
                {"id": _safe_id(name, seen), "field": field, "label": label, "granularity": "day"}
            )
        elif _is_metric(name, column_type):
            metrics.append(
                {
                    "id": _safe_id(f"{_aggregation_for_column(name)}_{name}", seen),
                    "field": field,
                    "label": label,
                    "aggregation": _aggregation_for_column(name),
                }
            )
        elif _is_dimension(name, column_type):
            dimensions.append({"id": _safe_id(name, seen), "field": field, "label": label})

    if not metrics:
        metrics.append({"id": _safe_id("count_all", seen), "field": "*", "label": "记录数", "aggregation": "count"})

    return normalize_semantic_model(
        {
            "dimensions": dimensions[:24],
            "metrics": metrics[:16],
            "time_dimensions": time_dimensions[:8],
            "synonyms": [],
        }
    )


def _semantic_from_payload(
    dataset: Any | None,
    table: str,
    fields_json: dict[str, Any] | None,
    aggregations_json: dict[str, Any] | None,
    semantic_model_json: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if isinstance(semantic_model_json, dict):
        return normalize_semantic_model(semantic_model_json)
    if isinstance(fields_json, dict) and (
        _as_list(fields_json.get("dimensions"))
        or _as_list(fields_json.get("fields"))
        or _as_list(fields_json.get("metrics"))
        or _as_list((aggregations_json or {}).get("aggregations"))
    ):
        dataset_like = SimpleNamespace(
            fields_json={**fields_json, "table": fields_json.get("table") or table},
            aggregations_json=aggregations_json,
            semantic_model_json=None,
        )
        return infer_semantic_model(dataset_like)
    if dataset is not None and isinstance(getattr(dataset, "semantic_model_json", None), dict):
        return normalize_semantic_model(dataset.semantic_model_json)
    if dataset is not None:
        try:
            return infer_semantic_model(dataset)
        except ValueError:
            return None
    return None


def _drill_from_semantic(semantic_model: dict[str, Any], default_table: str) -> dict[str, Any]:
    dimensions: list[dict[str, Any]] = []
    for item in semantic_model.get("dimensions", []) + semantic_model.get("time_dimensions", []):
        field = _clean(item.get("field"))
        column = _column_name(field)
        is_time = item in semantic_model.get("time_dimensions", [])
        dimensions.append(
            {
                "id": item["id"],
                "table": _table_name(field, default_table),
                "column": column,
                "label": item.get("label") or item["id"],
                "kind": _kind_for_dimension(column, is_time=is_time),
                "enabled": True,
            }
        )

    metrics: list[dict[str, Any]] = []
    for item in semantic_model.get("metrics", []):
        field = _clean(item.get("field"))
        column = "*" if field == "*" else _column_name(field)
        metrics.append(
            {
                "id": item["id"],
                "table": _table_name(field, default_table) if field != "*" else default_table,
                "column": column,
                "label": item.get("label") or item["id"],
                "aggregation": item.get("aggregation") or "sum",
                "enabled": True,
            }
        )

    paths: list[dict[str, Any]] = []
    non_time_dimensions = [item for item in dimensions if item["kind"] != "time"]
    time_dimensions = [item for item in dimensions if item["kind"] == "time"]
    for source in non_time_dimensions:
        targets = [item for item in non_time_dimensions if item["id"] != source["id"]] + time_dimensions[:1]
        for target in targets[:4]:
            path_id = f"{source['id']}__{target['id']}"
            if any(item["id"] == path_id for item in paths):
                continue
            paths.append(
                {
                    "id": path_id,
                    "source_dimension_id": source["id"],
                    "target_dimension_id": target["id"],
                    "label": f"看{target['label']}分布" if target["kind"] != "time" else "看时间趋势",
                    "action": "group_by",
                    "enabled": True,
                }
            )
    return normalize_drill_config({"dimensions": dimensions, "metrics": metrics, "paths": paths[:40]})


def _field_roles_from_semantic(semantic_model: dict[str, Any]) -> list[dict[str, Any]]:
    roles: list[dict[str, Any]] = []
    for item in semantic_model.get("dimensions", []) + semantic_model.get("time_dimensions", []):
        roles.append(
            {
                "field": item.get("field"),
                "role": "dimension",
                "alias": item.get("label") or item.get("id"),
            }
        )
    for item in semantic_model.get("metrics", []):
        roles.append(
            {
                "field": item.get("field"),
                "role": "metric",
                "alias": item.get("label") or item.get("id"),
                "aggregation": str(item.get("aggregation") or "sum").upper(),
            }
        )
    return roles


def _extract_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if "```" in text:
        matches = re.findall(r"```(?:json)?\n(.*?)```", text, re.S)
        if matches:
            text = matches[0].strip()
    return json.loads(text)


def _coerce_drill_config(raw: Any, default_table: str) -> dict[str, Any]:
    """将 LLM 可能输出的简化格式归一化为 DrillConfig 合法结构。

    兼容的简化写法：
      - dimensions/metrics 为纯字符串列表（缺省 table/column/label/kind/aggregation）
      - paths 使用 {"from": ..., "to": ...} 简写（缺 id/label/action）
    对合法标准结构保持幂等。
    """
    if not isinstance(raw, dict):
        raise ValueError("下钻配置必须是 JSON 对象")
    dimensions: list[dict[str, Any]] = []
    for item in _as_list(raw.get("dimensions")):
        if isinstance(item, str):
            item = {"id": item, "column": item}
        if not isinstance(item, dict):
            continue
        field = _clean(item.get("field") or item.get("column") or item.get("id"))
        if not field:
            continue
        column = _column_name(field)
        dimensions.append(
            {
                "id": item.get("id") or field,
                "table": _table_name(field, default_table),
                "column": column,
                "label": item.get("label") or column,
                "kind": item.get("kind") or _kind_for_dimension(column, is_time=_is_time(column, "")),
            }
        )

    metrics: list[dict[str, Any]] = []
    for item in _as_list(raw.get("metrics")):
        if isinstance(item, str):
            item = {"id": item, "column": item}
        if not isinstance(item, dict):
            continue
        field = _clean(item.get("field") or item.get("column") or item.get("id"))
        if not field:
            continue
        column = "*" if field == "*" else _column_name(field)
        metrics.append(
            {
                "id": item.get("id") or field,
                "table": _table_name(field, default_table) if field != "*" else default_table,
                "column": column,
                "label": item.get("label") or column,
                "aggregation": item.get("aggregation")
                or ("count" if column == "*" else _aggregation_for_column(column)),
            }
        )

    kind_by_id = {item["id"]: item["kind"] for item in dimensions}
    paths: list[dict[str, Any]] = []
    for item in _as_list(raw.get("paths")):
        if not isinstance(item, dict):
            continue
        source = _clean(item.get("source_dimension_id") or item.get("from"))
        target = _clean(item.get("target_dimension_id") or item.get("to"))
        if not source or not target or source == target:
            continue
        label = item.get("label")
        if not label:
            label = "看时间趋势" if kind_by_id.get(target) == "time" else f"看{target}分布"
        paths.append(
            {
                "id": item.get("id") or f"{source}__{target}",
                "source_dimension_id": source,
                "target_dimension_id": target,
                "label": label,
                "action": item.get("action") or "group_by",
            }
        )
    return {"dimensions": dimensions, "metrics": metrics, "paths": paths}


def _llm_prompt(datasource: Any, table: str, semantic_model: dict[str, Any], drill_config: dict[str, Any]) -> list[dict[str, str]]:
    schema = _schema_dict(datasource)
    system_prompt = """你是企业 BI 数据集建模助手。请为当前数据集生成可编辑的语义层和下钻配置。

要求：
1. 维度、指标、时间维度必须只使用给定 schema 中存在的字段。
2. 指标优先抽象为稳定口径，例如 COUNT(*)、SUM(total)、AVG(rate)，不要包含 TOP N 或临时时间过滤。
3. 下钻路径必须引用 semantic_model 中存在的维度或时间维度 ID。
4. 输出纯 JSON，不要 markdown。每个对象的字段必须完整给出，禁止把对象缩写成字符串数组，禁止用 from/to 简写路径。

必须输出的完整结构（字段一个都不能少）：
{
  "semantic_model": {
    "dimensions": [
      {"id": "site", "field": "cb_orders.site", "label": "站点"}
    ],
    "metrics": [
      {"id": "sum_gmv", "field": "cb_orders.amount", "label": "GMV", "aggregation": "sum"}
    ],
    "time_dimensions": [
      {"id": "dt", "field": "cb_orders.order_date", "label": "下单日期", "granularity": "day"}
    ],
    "synonyms": []
  },
  "drill_config": {
    "dimensions": [
      {"id": "site", "table": "cb_orders", "column": "site", "label": "站点", "kind": "site"}
    ],
    "metrics": [
      {"id": "sum_gmv", "table": "cb_orders", "column": "amount", "label": "GMV", "aggregation": "sum"}
    ],
    "paths": [
      {"id": "site__dt", "source_dimension_id": "site", "target_dimension_id": "dt", "label": "看时间趋势", "action": "group_by"}
    ]
  }
}
"""
    user_prompt = json.dumps(
        {
            "datasource": getattr(datasource, "name", ""),
            "table": table,
            "schema_metadata": schema,
            "current_semantic_model": semantic_model,
            "current_drill_config": drill_config,
        },
        ensure_ascii=False,
    )
    return [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]


async def suggest_dataset_ai_config(
    datasource: Any,
    dataset: Any | None = None,
    table: str | None = None,
    fields_json: dict[str, Any] | None = None,
    aggregations_json: dict[str, Any] | None = None,
    semantic_model_json: dict[str, Any] | None = None,
    drill_config_json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fields_json = fields_json if isinstance(fields_json, dict) else {}
    dataset_fields = getattr(dataset, "fields_json", None)
    dataset_table = dataset_fields.get("table") if isinstance(dataset_fields, dict) else ""
    table = _clean(table or fields_json.get("table") or dataset_table)
    if not table:
        schema = _schema_dict(datasource)
        first_table = _as_list(schema.get("tables"))[:1]
        table = _clean(first_table[0].get("name")) if first_table else ""

    warnings: list[str] = []
    semantic_model = _semantic_from_payload(dataset, table, fields_json, aggregations_json, semantic_model_json)
    if semantic_model is None:
        semantic_model = _semantic_from_schema(datasource, table)
        warnings.append("未找到现有语义层，已基于表结构生成规则草稿。")

    try:
        drill_config = normalize_drill_config(drill_config_json)
    except Exception:
        existing = getattr(dataset, "drill_config_json", None) if dataset is not None else None
        try:
            drill_config = normalize_drill_config(existing)
        except Exception:
            drill_config = _drill_from_semantic(semantic_model, table)

    source = "rule"
    try:
        raw = await chat_completion(_llm_prompt(datasource, table, semantic_model, drill_config), temperature=0.1)
        parsed = _extract_json(raw)
        llm_semantic = normalize_semantic_model(parsed.get("semantic_model") or {})
        llm_drill = normalize_drill_config(_coerce_drill_config(parsed.get("drill_config") or {}, table))
        semantic_model = llm_semantic
        drill_config = llm_drill
        source = "llm"
    except Exception as exc:
        warnings.append(f"大模型自动配置失败，已使用规则草稿: {exc}")

    return {
        "semantic_model": semantic_model,
        "field_roles": _field_roles_from_semantic(semantic_model),
        "drill_config": drill_config,
        "warnings": warnings,
        "source": source,
    }
