import json
import re
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.api.auth import get_current_user
from app.core.llm import chat_completion, get_llm_config, normalize_llm_config
from app.db.session import get_datasource_engine, get_db
from app.core.audit import try_record_audit_log
from app.core.permissions import has_action_permission, require_org_admin_or_above
from app.core.safe_delete import assert_metric_can_delete, delete_catalog_asset
from app.models.catalog import DataAsset
from app.models.datasource import DataSource
from app.models.dataset import Dataset
from app.models.metric import Metric
from app.models.organization import Organization
from app.models.query import QueryHistory
from app.models.user import User
from app.schemas.metric import (
    MetricCreate,
    MetricFromQueryCreateRequest,
    MetricFromQueryDraftRequest,
    MetricFromQueryDraftResponse,
    MetricPreviewRequest,
    MetricPreviewResponse,
    MetricUpdate,
    MetricOut,
    MetricListResponse,
)
from app.core.metric_formula import generate_metric_formula
from app.core.metric_prompt_sync import sync_datasource_metrics_prompt

router = APIRouter(prefix="/metrics", tags=["metrics"])

VALID_METRIC_STATUSES = {"draft", "published", "archived"}
VALID_CERTIFICATION_STATUSES = {"draft", "pending_review", "certified", "deprecated"}
VALID_QUALITY_STATUSES = {"unknown", "normal", "stale", "error"}
FILTER_OPERATORS = {"=", "!=", ">", ">=", "<", "<=", "LIKE", "NOT LIKE", "IN", "NOT IN", "IS NULL", "IS NOT NULL"}


def ensure_admin(user: User):
    if user.role != "super_admin":
        raise HTTPException(status_code=403, detail="无权限")


def _get_datasource_or_404(db: Session, datasource_id: int) -> DataSource:
    datasource = db.query(DataSource).filter(DataSource.id == datasource_id).first()
    if not datasource:
        raise HTTPException(status_code=404, detail="数据源不存在")
    return datasource


def _get_dataset_or_404(db: Session, dataset_id: int) -> Dataset:
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")
    return dataset


def _resolve_dataset_binding(db: Session, dataset_id: int) -> tuple[Dataset, DataSource]:
    dataset = _get_dataset_or_404(db, dataset_id)
    datasource = _get_datasource_or_404(db, dataset.datasource_id)
    return dataset, datasource


def _ensure_metric_values(status: str | None = None, certification_status: str | None = None, quality_status: str | None = None) -> None:
    if status is not None and status not in VALID_METRIC_STATUSES:
        raise HTTPException(status_code=400, detail="无效指标发布状态")
    if certification_status is not None and certification_status not in VALID_CERTIFICATION_STATUSES:
        raise HTTPException(status_code=400, detail="无效指标认证状态")
    if quality_status is not None and quality_status not in VALID_QUALITY_STATUSES:
        raise HTTPException(status_code=400, detail="无效指标质量状态")


def _safe_column_ref(value: object) -> str | None:
    text = str(value or "").strip()
    if not text or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*", text):
        return None
    return text


def _sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value).replace("'", "''")
    return f"'{text}'"


def _render_calculation_filters(calculation_config: dict | None) -> str:
    if not isinstance(calculation_config, dict):
        return ""
    clauses: list[str] = []
    for raw_rule in calculation_config.get("filters") or []:
        if not isinstance(raw_rule, dict):
            continue
        field = _safe_column_ref(raw_rule.get("field"))
        operator = str(raw_rule.get("operator") or "=").strip().upper()
        if not field or operator not in FILTER_OPERATORS:
            continue
        if operator in {"IS NULL", "IS NOT NULL"}:
            clause = f"{field} {operator}"
        elif operator in {"IN", "NOT IN"}:
            raw_value = raw_rule.get("value")
            values = raw_value if isinstance(raw_value, list) else str(raw_value or "").split(",")
            rendered_values = [_sql_literal(item) for item in values if str(item).strip()]
            if not rendered_values:
                continue
            clause = f"{field} {operator} ({', '.join(rendered_values)})"
        else:
            clause = f"{field} {operator} {_sql_literal(raw_rule.get('value'))}"
        logic = str(raw_rule.get("logic") or "AND").upper()
        if clauses and logic == "OR":
            clauses.append(f"OR {clause}")
        elif clauses:
            clauses.append(f"AND {clause}")
        else:
            clauses.append(clause)
    return " ".join(clauses)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _split_field_list(value: Any) -> list[str]:
    if isinstance(value, list):
        raw_items = value
    else:
        raw_items = re.split(r"[,，;\n]", str(value or ""))
    return [str(item).strip() for item in raw_items if str(item).strip()]


def _field_name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or value.get("field") or value.get("column") or "").strip()
    return str(value or "").strip()


def _field_label(value: Any, fallback: str) -> str:
    if isinstance(value, dict):
        return str(value.get("label") or value.get("alias") or value.get("display_name") or "").strip()
    return fallback.split(".")[-1] if fallback else ""


def _field_type(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("type") or value.get("data_type") or value.get("column_type") or "").strip()
    return ""


def _dataset_field_items(fields_json: dict[str, Any]) -> list[dict[str, str]]:
    items: list[Any] = []
    for key in ("dimensions", "fields", "metrics", "measures"):
        items.extend(_as_list(fields_json.get(key)))
    seen: set[str] = set()
    fields: list[dict[str, str]] = []
    for item in items:
        name = _field_name(item)
        if not name or name in seen:
            continue
        seen.add(name)
        fields.append({"name": name, "label": _field_label(item, name), "type": _field_type(item)})
    return fields


def _dataset_join_items(dataset: Dataset | None, fields_json: dict[str, Any]) -> list[dict[str, str]]:
    raw_joins: list[Any] = []
    raw_joins.extend(_as_list(fields_json.get("joins")))
    if dataset is not None:
        raw_joins.extend(_as_list(getattr(dataset, "joins_json", None)))

    joins: list[dict[str, str]] = []
    for item in raw_joins:
        if isinstance(item, dict):
            table = str(item.get("right") or item.get("table") or item.get("name") or "").strip()
            join_type = str(item.get("type") or item.get("join_type") or "JOIN").strip()
            join_on = str(item.get("on") or item.get("condition") or item.get("join_on") or "").strip()
        else:
            table = str(item or "").strip()
            join_type = "JOIN"
            join_on = ""
        if table:
            joins.append({"table": table, "join_type": join_type, "join_on": join_on})
    return joins


def _calculation_config(metric: Metric) -> dict[str, Any]:
    return _as_dict(metric.calculation_config)


def _metric_scope(metric: Metric) -> dict[str, Any]:
    config = _calculation_config(metric)
    structured_scope = _as_dict(config.get("statistical_scope"))
    filters = [item for item in _as_list(config.get("filters")) if isinstance(item, dict) and item.get("field")]
    return {
        "statistical_window": config.get("statistical_window") or structured_scope.get("statistical_window"),
        "time_field": config.get("time_field") or structured_scope.get("time_field"),
        "time_grain": config.get("time_grain") or structured_scope.get("time_grain"),
        "refresh_sla": config.get("refresh_sla") or structured_scope.get("refresh_sla"),
        "filters": filters,
        "dimensions": metric.dimensions or structured_scope.get("dimensions") or [],
        "included_subjects": structured_scope.get("included_subjects") or [],
        "excluded_subjects": structured_scope.get("excluded_subjects") or [],
        "organization_scope": structured_scope.get("organization_scope"),
    }


def _metric_source_fields(metric: Metric) -> list[str]:
    config = _calculation_config(metric)
    fields = [
        metric.column_name,
        config.get("metric_field"),
        config.get("numerator_field"),
        config.get("denominator_field"),
        config.get("derived_left_field"),
        config.get("derived_right_field"),
        config.get("time_field"),
    ]
    fields.extend(_split_field_list(config.get("partition_by")))
    fields.extend(_split_field_list(config.get("order_by")))
    fields.extend(rule.get("field") for rule in _as_list(config.get("filters")) if isinstance(rule, dict))
    seen: set[str] = set()
    normalized: list[str] = []
    for item in fields:
        text = str(item or "").strip()
        if text and text not in seen:
            seen.add(text)
            normalized.append(text)
    return normalized


def _metric_calculation_summary(metric: Metric) -> dict[str, Any]:
    config = _calculation_config(metric)
    mode = str(config.get("calculation_mode") or "aggregate")
    summary: dict[str, Any] = {
        "mode": mode,
        "aggregation": metric.aggregation,
        "source_fields": _metric_source_fields(metric),
    }
    for key in (
        "metric_field",
        "numerator_field",
        "numerator_aggregation",
        "denominator_field",
        "denominator_aggregation",
        "derived_left_field",
        "derived_operator",
        "derived_right_field",
        "dependency_metrics",
        "window_function",
        "partition_by",
        "order_by",
        "order_direction",
        "window_frame",
        "decimal_precision",
        "output_alias",
    ):
        if config.get(key) not in (None, ""):
            summary[key] = config.get(key)
    return summary


def _dependency_metric_refs(metric: Metric) -> tuple[list[int], list[str]]:
    config = _calculation_config(metric)
    operand_refs = [
        config.get("derived_left_field"),
        config.get("derived_right_field"),
    ]
    ids: list[int] = []
    names: list[str] = []
    for raw in operand_refs:
        text = str(raw or "").strip()
        if text.startswith("metric:"):
            try:
                ids.append(int(text.split(":", 1)[1]))
            except ValueError:
                continue
    for text in _split_field_list(config.get("dependency_metrics")):
        if text.startswith("metric:"):
            try:
                ids.append(int(text.split(":", 1)[1]))
            except ValueError:
                continue
        else:
            names.append(text)
    return ids, names


def _metric_dependencies(db: Session, metric: Metric) -> list[dict[str, Any]]:
    ids, names = _dependency_metric_refs(metric)
    if not ids and not names:
        return []
    query = db.query(Metric).filter(Metric.id != metric.id)
    clauses = []
    if ids:
        clauses.append(Metric.id.in_(ids))
    if names:
        clauses.append(Metric.name.in_(names))
    if not clauses:
        return []
    from sqlalchemy import or_

    rows = query.filter(or_(*clauses)).order_by(Metric.id).all()
    return [
        {
            "id": item.id,
            "name": item.name,
            "formula": item.formula,
            "caliber_version": item.caliber_version,
            "certification_status": item.certification_status,
            "quality_status": item.quality_status,
        }
        for item in rows
    ]


def _metric_preview_limit(limit: int) -> int:
    return max(1, min(int(limit or 50), 200))


def _source_table(dataset: Dataset) -> str:
    fields_json = _as_dict(dataset.fields_json)
    table = str(fields_json.get("table") or "").strip()
    if not table:
        for item in _dataset_field_items(fields_json):
            name = item["name"]
            if "." in name:
                table = name.split(".", 1)[0]
                break
    if not _safe_column_ref(table):
        raise HTTPException(status_code=400, detail="数据集缺少合法主表配置")
    return table


def _metric_dimension_candidates(dataset: Dataset) -> dict[str, str]:
    fields_json = _as_dict(dataset.fields_json)
    raw_items: list[Any] = []
    raw_items.extend(_as_list(fields_json.get("dimensions")))
    if not raw_items:
        raw_items.extend(_as_list(fields_json.get("fields")))
    semantic_model = _as_dict(dataset.semantic_model_json)
    raw_items.extend(_as_list(semantic_model.get("dimensions")))
    raw_items.extend(_as_list(semantic_model.get("time_dimensions")))

    table = str(fields_json.get("table") or "").strip()
    candidates: dict[str, str] = {}
    for item in raw_items:
        name = _field_name(item)
        if not name:
            continue
        if "." not in name and table:
            qualified_name = f"{table}.{name}"
            candidates.setdefault(qualified_name, _field_label(item, name) or name)
        candidates.setdefault(name, _field_label(item, name) or name.split(".")[-1])
    return candidates


def _metric_preview_alias(value: str) -> str:
    alias = str(value or "").strip()
    if not alias:
        raise HTTPException(status_code=400, detail="预览字段别名不合法")
    if len(alias) > 128 or any(token in alias for token in (";", "--", "/*", "*/", "\x00")):
        raise HTTPException(status_code=400, detail="预览字段别名不合法")
    return alias


def _quote_alias(alias: str) -> str:
    return f'"{alias.replace("\"", "\"\"")}"'


def _sanitize_formula_expression(formula: str) -> tuple[str, list[str]]:
    expression = str(formula or "").strip()
    if not expression:
        return "", []
    if any(token in expression for token in (";", "--", "/*", "*/", "\x00")):
        raise HTTPException(status_code=400, detail="指标公式包含不支持的 SQL 片段")
    where_parts: list[str] = []
    match = re.search(r"\bwhere\b", expression, flags=re.I)
    if match:
        where_parts.append(expression[match.end():].strip())
        expression = expression[:match.start()].strip()
    if not expression:
        raise HTTPException(status_code=400, detail="指标公式不能为空")
    return expression, where_parts


def _aggregation_expression(metric: Metric) -> str:
    formula_expression, _where_parts = _sanitize_formula_expression(metric.formula or "")
    if formula_expression:
        return formula_expression
    column = _safe_column_ref(metric.column_name)
    if not column:
        raise HTTPException(status_code=400, detail="指标缺少可预览的公式或字段")
    aggregation = str(metric.aggregation or "sum").strip().lower()
    if aggregation == "count_distinct":
        return f"COUNT(DISTINCT {column})"
    if aggregation == "count":
        return f"COUNT({column})"
    if aggregation in {"sum", "avg", "max", "min"}:
        return f"{aggregation.upper()}({column})"
    raise HTTPException(status_code=400, detail="指标聚合方式不支持预览")


def _render_preview_joins(dataset: Dataset, table: str) -> list[str]:
    joins: list[str] = []
    seen: set[str] = set()
    for item in _dataset_join_items(dataset, _as_dict(dataset.fields_json)):
        join_table = _safe_column_ref(item.get("table"))
        if not join_table or join_table == table:
            continue
        join_type = re.sub(r"\s+", " ", str(item.get("join_type") or "JOIN").upper()).strip()
        if join_type not in {"JOIN", "INNER JOIN", "LEFT JOIN", "LEFT OUTER JOIN", "RIGHT JOIN", "RIGHT OUTER JOIN", "FULL JOIN", "FULL OUTER JOIN"}:
            raise HTTPException(status_code=400, detail="数据集 Join 类型不支持预览")
        join_on = str(item.get("join_on") or "").strip()
        if not join_on or any(token in join_on for token in (";", "--", "/*", "*/", "\x00")):
            raise HTTPException(status_code=400, detail="数据集 Join 条件不合法")
        rendered = f"{join_type} {join_table} ON {join_on}"
        if rendered not in seen:
            seen.add(rendered)
            joins.append(rendered)
    return joins


def _metric_preview_plan(metric: Metric, dataset: Dataset, datasource: DataSource, payload: MetricPreviewRequest) -> dict[str, Any]:
    table = _source_table(dataset)
    dimension_candidates = _metric_dimension_candidates(dataset)
    selected_dimensions: list[dict[str, str]] = []
    for raw_dimension in payload.dimensions or []:
        field = _safe_column_ref(raw_dimension)
        if not field:
            raise HTTPException(status_code=400, detail="预览维度字段不合法")
        label = dimension_candidates.get(field) or dimension_candidates.get(field.split(".")[-1])
        if not label:
            raise HTTPException(status_code=400, detail=f"预览维度不属于当前指标数据集: {raw_dimension}")
        selected_dimensions.append({"field": field, "label": _metric_preview_alias(label)})

    metric_alias = _metric_preview_alias(metric.name)
    formula_expression, formula_where_parts = _sanitize_formula_expression(metric.formula or "")
    metric_expression = formula_expression or _aggregation_expression(metric)
    select_parts = [
        f"{item['field']} AS {_quote_alias(item['label'])}"
        for item in selected_dimensions
    ]
    select_parts.append(f"{metric_expression} AS {_quote_alias(metric_alias)}")

    where_parts = formula_where_parts
    filters_sql = _render_calculation_filters(metric.calculation_config)
    if filters_sql:
        where_parts.append(filters_sql)

    is_window_metric = str(_calculation_config(metric).get("calculation_mode") or "").lower() == "window" or re.search(r"\bover\s*\(", metric_expression, flags=re.I)
    group_parts = [item["field"] for item in selected_dimensions] if selected_dimensions and not is_window_metric else []
    limit = _metric_preview_limit(payload.limit)
    sql_parts = [
        f"SELECT {', '.join(select_parts)}",
        f"FROM {table}",
        *_render_preview_joins(dataset, table),
    ]
    if where_parts:
        sql_parts.append(f"WHERE {' AND '.join(where_parts)}")
    if group_parts:
        sql_parts.append(f"GROUP BY {', '.join(group_parts)}")
    sql_parts.append(f"ORDER BY {_quote_alias(metric_alias)} DESC")
    sql_parts.append(f"LIMIT {limit}")
    return {
        "sql": "\n".join(sql_parts),
        "dimensions": [item["field"] for item in selected_dimensions],
        "dimension_labels": [item["label"] for item in selected_dimensions],
        "metric_column": metric_alias,
        "limit": limit,
    }


def _execute_metric_preview(datasource: DataSource, plan: dict[str, Any]) -> dict[str, Any]:
    sql = plan["sql"]
    if datasource.source_type == "excel":
        from app.core.excel_executor import execute_excel_query

        return execute_excel_query(datasource.database_url, sql)

    engine = get_datasource_engine(datasource.database_url)
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        columns = list(result.keys())
        rows = [dict(row._mapping) for row in result.fetchall()]
    return {"columns": columns, "rows": rows}


def _apply_metric_visibility(query, user: User):
    if user.role == "super_admin":
        return query
    return query.join(DataSource, Metric.datasource_id == DataSource.id).filter(DataSource.org_id == user.org_id)


def _certifier_can_certify(user: User) -> bool:
    return has_action_permission(user, "metric.certify")


def _validate_metric_certifier(db: Session, certified_by: str | None, datasource: DataSource | None) -> str | None:
    if not certified_by:
        return None
    certifier = db.query(User).filter(User.username == certified_by).first()
    if not certifier:
        raise HTTPException(status_code=400, detail="认证人不存在")
    if not _certifier_can_certify(certifier):
        raise HTTPException(status_code=400, detail="认证人没有指标认证权限")
    if datasource and datasource.org_id and certifier.role != "super_admin" and certifier.org_id != datasource.org_id:
        raise HTTPException(status_code=400, detail="认证人不属于指标所在企业")
    return certifier.username


def _touch_certification(
    metric: Metric,
    current_user: User,
    previous_status: str | None = None,
    previous_certified_by: str | None = None,
) -> None:
    if metric.certification_status != "certified":
        return
    if previous_status == "certified" and metric.certified_at and metric.certified_by == previous_certified_by:
        return
    if not metric.certified_by:
        metric.certified_by = getattr(current_user, "username", None) or getattr(current_user, "name", None)
    metric.certified_at = datetime.utcnow()


def _supports_catalog_sync(db: Session) -> bool:
    return hasattr(db, "get_bind") and hasattr(db, "flush")


def _sync_metric_catalog_asset(db: Session, metric: Metric, datasource: DataSource | None = None) -> None:
    if not _supports_catalog_sync(db):
        return

    datasource = datasource or (
        db.query(DataSource).filter(DataSource.id == metric.datasource_id).first()
        if metric.datasource_id
        else None
    )
    asset = (
        db.query(DataAsset)
        .filter(DataAsset.asset_type == "metric", DataAsset.asset_id == metric.id)
        .first()
    )
    if not asset:
        asset = DataAsset(asset_type="metric", asset_id=metric.id, name=metric.name)
        db.add(asset)

    asset.name = metric.name
    asset.description = metric.description or metric.definition
    asset.datasource_id = metric.datasource_id
    asset.org_id = datasource.org_id if datasource else None
    asset.status = metric.status or "draft"
    asset.tags = metric.tags
    asset.metadata_json = {
        "definition": metric.definition,
        "formula": metric.formula,
        "calculation_config": metric.calculation_config,
        "statistical_scope": _metric_scope(metric),
        "column_name": metric.column_name,
        "owner_name": metric.owner_name,
        "unit": metric.unit,
        "aggregation": metric.aggregation,
        "dimensions": metric.dimensions,
        "certification_status": metric.certification_status,
        "certified_by": metric.certified_by,
        "certified_at": metric.certified_at.isoformat() if metric.certified_at else None,
        "caliber_version": metric.caliber_version,
        "data_updated_at": metric.data_updated_at.isoformat() if metric.data_updated_at else None,
        "quality_status": metric.quality_status,
        "quality_message": metric.quality_message,
        "is_active": metric.is_active,
    }
    db.flush()


def _delete_metric_catalog_asset(db: Session, metric_id: int) -> None:
    if not _supports_catalog_sync(db):
        return
    delete_catalog_asset(db, "metric", metric_id)


def _record_metric_audit(db: Session, current_user: User, action: str, metric: Metric | None = None, **extra) -> None:
    if not _supports_catalog_sync(db):
        return
    try_record_audit_log(
        db,
        actor=current_user,
        action=action,
        resource_type="metric",
        resource_id=getattr(metric, "id", extra.get("resource_id")),
        resource_name=getattr(metric, "name", extra.get("resource_name")),
        org_id=extra.get("org_id"),
        message=extra.get("message"),
        detail=extra.get("detail"),
    )


def _extract_json_object(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, flags=re.S)
        if match:
            return _extract_json_object(match.group(1))
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                parsed = json.loads(raw[start : end + 1])
                return parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                return {}
        return {}


def _clean_query_history_question(question: str | None) -> str:
    return re.sub(r"^\[(SQL|闲聊|业务问数|探索问数|探索模式|Agentic问数)\]\s*", "", str(question or "")).strip()


def _metric_from_query_permission(current_user: User) -> None:
    if getattr(current_user, "role", None) == "department_admin":
        return
    if not has_action_permission(current_user, "metric.create"):
        raise HTTPException(status_code=403, detail="需要指标创建权限")


def _query_history_for_metric_draft(db: Session, history_id: int, current_user: User) -> tuple[QueryHistory, DataSource]:
    history = db.query(QueryHistory).filter(QueryHistory.id == history_id).first()
    if not history:
        raise HTTPException(status_code=404, detail="查询历史不存在")
    datasource = (
        db.query(DataSource).filter(DataSource.id == history.datasource_id).first()
        if history.datasource_id
        else None
    )
    if not datasource:
        raise HTTPException(status_code=400, detail="查询历史未绑定数据源")
    if getattr(current_user, "role", None) != "super_admin" and datasource.org_id != getattr(current_user, "org_id", None):
        raise HTTPException(status_code=404, detail="查询历史不存在")
    return history, datasource


def _dataset_visible_for_metric_source(dataset: Dataset, current_user: User) -> bool:
    role = getattr(current_user, "role", None)
    if role == "super_admin":
        return True
    if dataset.org_id != getattr(current_user, "org_id", None):
        return False
    if role == "org_admin":
        return True
    if role == "dept_admin":
        return dataset.status in {"published", "pending_review"} or dataset.owner_id == getattr(current_user, "id", None)
    return dataset.status == "published" or dataset.owner_id == getattr(current_user, "id", None)


def _dataset_recommendation_rank(dataset: Dataset) -> tuple[int, int, int, int]:
    status_rank = {"published": 0, "pending_review": 1, "draft": 2}.get(dataset.status or "", 3)
    visibility_rank = {"org": 0, "private": 1}.get(dataset.visibility or "", 2)
    materialized_rank = 0 if dataset.materialized_table_name or dataset.materialization_status == "success" else 1
    return (status_rank, visibility_rank, materialized_rank, -(dataset.id or 0))


def _resolve_metric_query_dataset(
    db: Session,
    datasource: DataSource,
    current_user: User,
    requested_dataset_id: int | None = None,
) -> Dataset:
    query = db.query(Dataset).filter(Dataset.datasource_id == datasource.id)
    if getattr(current_user, "role", None) != "super_admin":
        query = query.filter(Dataset.org_id == getattr(current_user, "org_id", None))
    candidates = [dataset for dataset in query.all() if _dataset_visible_for_metric_source(dataset, current_user)]

    if requested_dataset_id:
        dataset = next((item for item in candidates if item.id == requested_dataset_id), None)
        if not dataset:
            raise HTTPException(status_code=400, detail="请选择当前数据源下可访问的同源数据集")
        return dataset

    if not candidates:
        raise HTTPException(status_code=400, detail="当前数据源下没有可绑定的同源数据集，请先创建基础数据集")
    return sorted(candidates, key=_dataset_recommendation_rank)[0]


def _history_result_payload(history: QueryHistory) -> dict[str, Any]:
    try:
        payload = json.loads(history.result_json or "{}")
    except json.JSONDecodeError:
        payload = {}
    return payload if isinstance(payload, dict) else {}


def _history_columns_and_rows(history: QueryHistory) -> tuple[list[str], list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    result = _history_result_payload(history)
    columns = [str(column) for column in result.get("columns", [])]
    rows = [row for row in (result.get("rows") or []) if isinstance(row, dict)]
    chart_spec = result.get("_chart_spec") if isinstance(result.get("_chart_spec"), dict) else {}
    agent_trace = [item for item in (result.get("_agent_trace") or []) if isinstance(item, dict)]
    return columns, rows, chart_spec, agent_trace


def _number_value(value: Any) -> float | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _numeric_columns(columns: list[str], rows: list[dict[str, Any]]) -> list[str]:
    numeric: list[str] = []
    for column in columns:
        values = [_number_value(row.get(column)) for row in rows[:50]]
        available = [value for value in values if value is not None]
        if available and len(available) >= max(1, min(len(rows), 50) // 2):
            numeric.append(column)
    return numeric


def _column_name_match(raw: Any, columns: list[str]) -> str | None:
    text = str(raw or "").strip()
    if not text:
        return None
    exact = {column.lower(): column for column in columns}
    return exact.get(text.lower())


def _normalize_column_list(raw_items: Any, columns: list[str]) -> list[str]:
    if isinstance(raw_items, str):
        items = re.split(r"[,，;\n]", raw_items)
    elif isinstance(raw_items, list):
        items = raw_items
    else:
        items = []
    normalized: list[str] = []
    for item in items:
        column = _column_name_match(item, columns)
        if column and column not in normalized:
            normalized.append(column)
    return normalized


def _looks_like_time_column(column: str) -> bool:
    lower = column.lower()
    return any(token in lower for token in ("date", "time", "day", "month", "year", "日期", "时间", "月份", "年度"))


def _preferred_metric_column(columns: list[str], rows: list[dict[str, Any]], selected: str | None, chart_spec: dict[str, Any]) -> str | None:
    selected_column = _column_name_match(selected, columns)
    if selected_column:
        return selected_column
    numeric = _numeric_columns(columns, rows)
    chart_y = _column_name_match(chart_spec.get("y_field"), columns)
    if chart_y in numeric:
        return chart_y
    metric_keywords = ("count", "cnt", "total", "sum", "amount", "qty", "rate", "ratio", "value", "times", "occurrence", "数量", "金额", "次数", "总计", "合计", "占比", "比率")
    for column in numeric:
        if any(keyword in column.lower() for keyword in metric_keywords):
            return column
    return numeric[0] if numeric else (columns[-1] if columns else None)


def _preferred_time_column(columns: list[str], selected: str | None, chart_spec: dict[str, Any]) -> str | None:
    selected_column = _column_name_match(selected, columns)
    if selected_column:
        return selected_column
    chart_x = _column_name_match(chart_spec.get("x_field"), columns)
    if chart_x and _looks_like_time_column(chart_x):
        return chart_x
    return next((column for column in columns if _looks_like_time_column(column)), None)


def _preferred_dimensions(
    columns: list[str],
    metric_column: str | None,
    time_column: str | None,
    selected_dimensions: list[str] | None,
    chart_spec: dict[str, Any],
) -> list[str]:
    selected = _normalize_column_list(selected_dimensions or [], columns)
    if selected:
        return [column for column in selected if column != metric_column]

    dimension_fields: list[str] = []
    for raw in [chart_spec.get("facet_field"), *(chart_spec.get("series_fields") or []), chart_spec.get("x_field")]:
        column = _column_name_match(raw, columns)
        if column and column not in {metric_column, time_column} and column not in dimension_fields:
            dimension_fields.append(column)
    if dimension_fields:
        return dimension_fields
    return [column for column in columns if column not in {metric_column, time_column}]


def _split_select_items(select_clause: str) -> list[str]:
    items: list[str] = []
    current: list[str] = []
    depth = 0
    quote: str | None = None
    for char in select_clause:
        if quote:
            current.append(char)
            if char == quote:
                quote = None
            continue
        if char in ("'", '"'):
            quote = char
            current.append(char)
            continue
        if char == "(":
            depth += 1
        elif char == ")" and depth:
            depth -= 1
        if char == "," and depth == 0:
            item = "".join(current).strip()
            if item:
                items.append(item)
            current = []
            continue
        current.append(char)
    item = "".join(current).strip()
    if item:
        items.append(item)
    return items


def _select_clause(sql: str) -> str:
    text_sql = str(sql or "").strip()
    matches = list(re.finditer(r"\bselect\b", text_sql, flags=re.I))
    if not matches:
        return ""
    start = matches[-1].end()
    from_match = re.search(r"\bfrom\b", text_sql[start:], flags=re.I)
    if not from_match:
        return ""
    return text_sql[start : start + from_match.start()].strip()


def _extract_formula_from_sql(sql: str, metric_column: str | None) -> str:
    metric_column = str(metric_column or "").strip()
    if not metric_column:
        return ""
    for item in _split_select_items(_select_clause(sql)):
        match = re.search(r"\s+as\s+([\"`']?)(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\1\s*$", item, flags=re.I)
        if match and match.group("alias").lower() == metric_column.lower():
            expression = item[: match.start()].strip()
            if expression and re.search(r"\b(count|sum|avg|min|max)\s*\(", expression, flags=re.I):
                return expression
    if re.search(r"\bcount\s*\(\s*\*\s*\)", sql, flags=re.I) and re.search(r"(count|cnt|times|occurrence|次数)", metric_column, flags=re.I):
        return "COUNT(*)"
    if _safe_column_ref(metric_column):
        return f"SUM({metric_column})"
    return ""


def _default_metric_name(question: str, metric_column: str | None) -> str:
    if re.search(r"alarm|报警", question, flags=re.I):
        return "报警发生次数"
    if metric_column:
        return metric_column.replace("_", " ").strip()[:64]
    return "探索沉淀指标"


def _default_unit(metric_column: str | None, formula: str) -> str | None:
    text = f"{metric_column or ''} {formula}".lower()
    if any(token in text for token in ("rate", "ratio", "percent", "率", "占比")):
        return "%"
    if any(token in text for token in ("count", "cnt", "times", "occurrence", "次数")):
        return "次"
    return None


def _analysis_condition_warnings(question: str, sql: str) -> list[str]:
    combined = f"{question}\n{sql}".lower()
    warnings: list[str] = []
    if re.search(r"\btop\s*\d+|top\d+|前\s*\d+|limit\s+\d+|row_number\s*\(|rank\s*\(", combined, flags=re.I):
        warnings.append("TOP N、排序截断或排名属于分析条件，不建议写入指标公式。")
    if re.search(r"最近|近\s*\d+|last\s+\d+|interval\s+'?\d+|date_sub", combined, flags=re.I):
        warnings.append("临时时间窗口属于分析条件，可作为默认分析视图条件保留。")
    return warnings


def _normalize_candidate(candidate: dict[str, Any], fallback: dict[str, Any], columns: list[str]) -> dict[str, Any]:
    normalized = dict(fallback)
    for key in ("name", "definition", "formula", "unit", "metric_column", "time_column"):
        value = str(candidate.get(key) or "").strip()
        if value:
            normalized[key] = value
    metric_column = _column_name_match(normalized.get("metric_column"), columns) or fallback.get("metric_column")
    time_column = _column_name_match(normalized.get("time_column"), columns) or fallback.get("time_column")
    normalized["metric_column"] = metric_column
    normalized["time_column"] = time_column
    dimensions = _normalize_column_list(candidate.get("dimensions"), columns) or fallback.get("dimensions") or []
    normalized["dimensions"] = [column for column in dimensions if column not in {metric_column, time_column}]
    normalized["warnings"] = [str(item).strip() for item in candidate.get("warnings", []) if str(item).strip()]
    normalized["name"] = str(normalized.get("name") or "探索沉淀指标").strip()[:128]
    normalized["definition"] = str(normalized.get("definition") or f"从探索模式问数结果沉淀的指标：{normalized['name']}").strip()
    normalized["formula"] = str(normalized.get("formula") or fallback.get("formula") or "").strip()
    if not normalized["formula"]:
        raise HTTPException(status_code=400, detail="未能从问数结果识别稳定指标公式")
    return normalized


async def _build_metric_from_query_draft(
    payload: MetricFromQueryDraftRequest,
    db: Session,
    current_user: User,
    *,
    use_llm: bool = True,
) -> dict[str, Any]:
    _metric_from_query_permission(current_user)
    history, datasource = _query_history_for_metric_draft(db, payload.query_history_id, current_user)
    columns, rows, chart_spec, agent_trace = _history_columns_and_rows(history)
    if not columns or not rows:
        raise HTTPException(status_code=400, detail="查询历史没有可沉淀的结果数据")
    dataset = _resolve_metric_query_dataset(db, datasource, current_user, payload.dataset_id)

    question = _clean_query_history_question(history.question)
    metric_column = _preferred_metric_column(columns, rows, payload.selected_metric_column, chart_spec)
    time_column = _preferred_time_column(columns, payload.time_column, chart_spec)
    dimensions = _preferred_dimensions(columns, metric_column, time_column, payload.selected_dimensions, chart_spec)
    formula = _extract_formula_from_sql(history.sql_query or "", metric_column)
    fallback = {
        "name": _default_metric_name(question, metric_column),
        "definition": f"从探索问题“{question[:80]}”沉淀的可复用指标",
        "formula": formula,
        "unit": _default_unit(metric_column, formula),
        "metric_column": metric_column,
        "dimensions": dimensions,
        "time_column": time_column,
        "warnings": [],
    }
    llm_enhanced = False
    llm_model = None
    llm_warnings: list[str] = []
    candidate = dict(fallback)

    if use_llm:
        try:
            llm_config = None
            try:
                llm_config = normalize_llm_config(await get_llm_config())
                llm_model = llm_config.get("model")
            except Exception:
                llm_config = None
            raw = await chat_completion(
                [
                    {
                        "role": "system",
                        "content": (
                            "你是企业 BI 指标建模助手。根据探索模式问数结果，提取可以沉淀为稳定指标的草稿。"
                            "不要把 TOP N、LIMIT、临时时间窗口或趋势分组写入指标公式；这些只能作为 warnings。"
                            "只输出严格 JSON，字段：name、definition、formula、unit、metric_column、dimensions、time_column、warnings。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "question": question,
                                "sql": history.sql_query,
                                "columns": columns,
                                "sample_rows": rows[:20],
                                "chart_spec": chart_spec,
                                "fallback": fallback,
                            },
                            ensure_ascii=False,
                            default=str,
                        ),
                    },
                ],
                temperature=0,
                config_override=llm_config,
            )
            parsed = _extract_json_object(raw)
            if parsed:
                candidate = _normalize_candidate(parsed, fallback, columns)
                llm_warnings = candidate.pop("warnings", [])
                llm_enhanced = True
        except Exception as exc:
            llm_warnings = [f"大模型指标识别失败，已使用规则草稿: {exc}"]
            candidate = _normalize_candidate({}, fallback, columns)
    else:
        candidate = _normalize_candidate({}, fallback, columns)

    warnings = []
    warnings.extend(_analysis_condition_warnings(question, history.sql_query or ""))
    warnings.extend(llm_warnings)
    deduped_warnings = list(dict.fromkeys(item for item in warnings if item))
    source = {
        "source_type": "agentic_query",
        "source_query_history_id": history.id,
        "source_dataset_id": dataset.id,
        "source_dataset_name": dataset.name,
        "source_datasource_id": datasource.id,
        "source_question": question,
        "source_sql": history.sql_query,
        "source_chart_spec": chart_spec,
        "source_agent_trace": agent_trace,
        "source_columns": columns,
        "source_metric_column": candidate.get("metric_column"),
        "dataset_binding": {
            "dataset_id": dataset.id,
            "dataset_name": dataset.name,
            "datasource_id": datasource.id,
            "auto_recommended": payload.dataset_id is None,
        },
    }
    validation = {
        "status": "draft",
        "validation_status": "passed" if candidate.get("formula") else "warning",
        "message": "已生成指标草稿，保存后可在指标中心继续完善和认证。",
        "row_count": len(rows),
    }
    return {
        "candidate": candidate,
        "source": source,
        "validation": validation,
        "warnings": deduped_warnings,
        "llm_enhanced": llm_enhanced,
        "llm_model": llm_model,
    }


def _metric_from_query_calculation_config(draft: dict[str, Any], source: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
    candidate = draft.get("candidate") or {}
    validation = draft.get("validation") or {}
    return {
        "calculation_mode": "aggregate",
        "metric_field": candidate.get("metric_column"),
        "output_alias": candidate.get("metric_column"),
        "time_field": candidate.get("time_column"),
        "time_grain": "day" if candidate.get("time_column") else "",
        "filters": [],
        "source": {
            **source,
            "validation_status": validation.get("validation_status"),
            "validation_message": validation.get("message"),
            "analysis_warnings": warnings,
        },
    }


@router.get("", response_model=MetricListResponse)
def list_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = _apply_metric_visibility(db.query(Metric), current_user)
    items = query.order_by(Metric.updated_at.desc(), Metric.id.desc()).all()
    return {"items": items}


@router.get("/certifiers")
def list_metric_certifiers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_org_admin_or_above(current_user)
    query = db.query(User)
    if current_user.role != "super_admin":
        query = query.filter(User.org_id == current_user.org_id)
    users = query.order_by(User.org_id, User.username).all()
    org_ids = {user.org_id for user in users if user.org_id}
    orgs = (
        db.query(Organization).filter(Organization.id.in_(org_ids)).all()
        if org_ids
        else []
    )
    org_names = {org.id: org.name for org in orgs}
    items = []
    for user in users:
        if not _certifier_can_certify(user):
            continue
        items.append(
            {
                "id": user.id,
                "username": user.username,
                "role": user.role,
                "department": getattr(user, "department", None),
                "org_id": user.org_id,
                "org_name": org_names.get(user.org_id),
                "can_certify_metric": True,
            }
        )
    return {"items": items}


@router.post("", response_model=MetricOut)
def create_metric(
    payload: MetricCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_admin(current_user)
    _ensure_metric_values(payload.status, payload.certification_status, payload.quality_status)
    _dataset, datasource = _resolve_dataset_binding(db, payload.dataset_id)
    existing = db.query(Metric).filter(Metric.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="指标名称已存在")
    data = payload.model_dump()
    data["datasource_id"] = datasource.id
    data["certified_by"] = _validate_metric_certifier(db, data.get("certified_by"), datasource)
    metric = Metric(**data)
    _touch_certification(metric, current_user)
    db.add(metric)
    db.commit()
    db.refresh(metric)
    _sync_metric_catalog_asset(db, metric, datasource)
    sync_datasource_metrics_prompt(db, datasource.id)
    db.commit()
    db.refresh(metric)
    _record_metric_audit(
        db,
        current_user,
        "metric.create",
        metric,
        org_id=getattr(datasource, "org_id", None),
        message="指标已创建",
        detail={"dataset_id": metric.dataset_id, "datasource_id": metric.datasource_id, "status": metric.status},
    )
    return metric


@router.post("/from-query/draft", response_model=MetricFromQueryDraftResponse)
async def draft_metric_from_query(
    payload: MetricFromQueryDraftRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await _build_metric_from_query_draft(payload, db, current_user)


@router.post("/from-query", response_model=MetricOut)
async def create_metric_from_query(
    payload: MetricFromQueryCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    selected_dimensions = payload.dimensions if payload.dimensions is not None else payload.selected_dimensions
    draft_payload = MetricFromQueryDraftRequest(
        query_history_id=payload.query_history_id,
        dataset_id=payload.dataset_id,
        selected_metric_column=payload.selected_metric_column,
        selected_dimensions=selected_dimensions or [],
        time_column=payload.time_column,
    )
    use_llm = not all([payload.name, payload.definition, payload.formula])
    draft = await _build_metric_from_query_draft(draft_payload, db, current_user, use_llm=use_llm)
    candidate = draft["candidate"]
    source = draft["source"]
    warnings = draft["warnings"]
    history, datasource = _query_history_for_metric_draft(db, payload.query_history_id, current_user)
    dataset = _resolve_metric_query_dataset(db, datasource, current_user, payload.dataset_id or source.get("source_dataset_id"))

    name = str(payload.name or candidate.get("name") or "").strip()[:128]
    definition = str(payload.definition or candidate.get("definition") or "").strip()
    formula = str(payload.formula or candidate.get("formula") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="指标名称不能为空")
    if not definition:
        raise HTTPException(status_code=400, detail="指标定义不能为空")
    if not formula:
        raise HTTPException(status_code=400, detail="指标公式不能为空")
    if db.query(Metric).filter(Metric.name == name).first():
        raise HTTPException(status_code=400, detail="指标名称已存在")

    status = payload.status or "draft"
    certification_status = payload.certification_status or "pending_review"
    _ensure_metric_values(status, certification_status, "unknown")
    dimensions = selected_dimensions or candidate.get("dimensions") or []
    metric = Metric(
        dataset_id=dataset.id,
        datasource_id=dataset.datasource_id,
        name=name,
        description=f"由探索模式问数沉淀：{_clean_query_history_question(history.question)[:120]}",
        definition=definition,
        column_name=candidate.get("metric_column"),
        formula=formula,
        calculation_config=_metric_from_query_calculation_config(draft, source, warnings),
        owner_name=payload.owner_name or getattr(current_user, "username", None),
        unit=payload.unit if payload.unit is not None else candidate.get("unit"),
        aggregation="count" if formula.upper().startswith("COUNT(") else "sum",
        tags=["探索沉淀"],
        status=status,
        dimensions=dimensions,
        certification_status=certification_status,
        caliber_version="v1",
        quality_status="unknown",
        is_active=1,
    )
    _touch_certification(metric, current_user)
    db.add(metric)
    db.commit()
    db.refresh(metric)
    _sync_metric_catalog_asset(db, metric, datasource)
    sync_datasource_metrics_prompt(db, datasource.id)
    db.commit()
    db.refresh(metric)
    _record_metric_audit(
        db,
        current_user,
        "metric.create_from_query",
        metric,
        org_id=getattr(datasource, "org_id", None),
        message="已从探索结果创建指标草稿",
        detail={
            "query_history_id": history.id,
            "dataset_id": dataset.id,
            "datasource_id": dataset.datasource_id,
            "status": metric.status,
            "certification_status": metric.certification_status,
        },
    )
    return metric


@router.get("/{metric_id}", response_model=MetricOut)
def get_metric(
    metric_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    metric = db.query(Metric).filter(Metric.id == metric_id).first()
    if not metric:
        raise HTTPException(status_code=404, detail="指标不存在")
    if current_user.role != "super_admin":
        datasource = db.query(DataSource).filter(DataSource.id == metric.datasource_id).first()
        if not datasource or datasource.org_id != current_user.org_id:
            raise HTTPException(status_code=404, detail="指标不存在")
    return metric


@router.get("/{metric_id}/lineage")
def get_metric_lineage(
    metric_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    metric = get_metric(metric_id, db=db, current_user=current_user)
    datasource = (
        db.query(DataSource).filter(DataSource.id == metric.datasource_id).first()
        if metric.datasource_id
        else None
    )
    dataset = (
        db.query(Dataset).filter(Dataset.id == metric.dataset_id).first()
        if metric.dataset_id
        else None
    )

    # Build dataset lineage info from fields_json plus joins_json.
    fields_json = (dataset.fields_json or {}) if dataset else {}
    main_table = str(fields_json.get("table") or "")
    dataset_fields = _dataset_field_items(fields_json)
    dataset_joins = _dataset_join_items(dataset, fields_json)

    return {
        "metric": {
            "id": metric.id,
            "name": metric.name,
            "definition": metric.definition,
            "formula": metric.formula,
            "calculation_config": metric.calculation_config,
            "unit": metric.unit,
            "aggregation": metric.aggregation,
            "caliber_version": metric.caliber_version,
            "owner_name": metric.owner_name,
        },
        "dataset": {
            "id": dataset.id if dataset else None,
            "name": dataset.name if dataset else None,
            "description": dataset.description if dataset else None,
            "main_table": main_table or None,
            "fields": dataset_fields,
            "joins": dataset_joins,
        },
        "datasource": {
            "id": datasource.id if datasource else None,
            "name": datasource.name if datasource else None,
            "source_type": datasource.source_type if datasource else None,
        },
        "source": {
            "table_name": main_table or None,
            "column_name": metric.column_name,
        },
        "trust": {
            "certification_status": metric.certification_status,
            "certified_by": metric.certified_by,
            "certified_at": metric.certified_at,
            "quality_status": metric.quality_status,
            "quality_message": metric.quality_message,
            "data_updated_at": metric.data_updated_at,
        },
        "scope": _metric_scope(metric),
        "calculation": _metric_calculation_summary(metric),
        "dependencies": _metric_dependencies(db, metric),
        "usage": {
            "catalog_asset": "metric",
            "datasource_id": metric.datasource_id,
        },
    }


@router.post("/{metric_id}/preview", response_model=MetricPreviewResponse)
def preview_metric(
    metric_id: int,
    payload: MetricPreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    metric = get_metric(metric_id, db=db, current_user=current_user)
    dataset = (
        db.query(Dataset).filter(Dataset.id == metric.dataset_id).first()
        if metric.dataset_id
        else None
    )
    if not dataset:
        raise HTTPException(status_code=400, detail="指标未绑定数据集，无法预览")
    datasource = (
        db.query(DataSource).filter(DataSource.id == metric.datasource_id).first()
        if metric.datasource_id
        else None
    )
    if not datasource:
        raise HTTPException(status_code=400, detail="指标未绑定数据源，无法预览")

    plan = _metric_preview_plan(metric, dataset, datasource, payload)
    try:
        result = _execute_metric_preview(datasource, plan)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"指标实时预览失败: {exc}")

    rows = result.get("rows", [])
    columns = list(result.get("columns", []))
    response = {
        "metric": {
            "id": metric.id,
            "name": metric.name,
            "caliber_version": metric.caliber_version,
            "formula": metric.formula,
        },
        "dataset": {"id": dataset.id, "name": dataset.name},
        "datasource": {"id": datasource.id, "name": datasource.name, "source_type": datasource.source_type},
        "dimensions": [
            {"field": field, "label": label}
            for field, label in zip(plan.get("dimensions", []), plan.get("dimension_labels", []))
        ],
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "query": {
            "sql": plan["sql"],
            "dimensions": plan.get("dimensions", []),
            "limit": plan.get("limit"),
            "metric_column": plan.get("metric_column"),
        },
    }
    return jsonable_encoder(response)


@router.put("/{metric_id}", response_model=MetricOut)
def update_metric(
    metric_id: int,
    payload: MetricUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_admin(current_user)
    metric = db.query(Metric).filter(Metric.id == metric_id).first()
    if not metric:
        raise HTTPException(status_code=404, detail="指标不存在")
    previous_datasource_id = metric.datasource_id
    previous_datasource = (
        db.query(DataSource).filter(DataSource.id == previous_datasource_id).first()
        if previous_datasource_id
        else None
    )
    values = payload.model_dump(exclude_unset=True)
    if "dataset_id" in values:
        _dataset, previous_datasource = _resolve_dataset_binding(db, values["dataset_id"])
        values["datasource_id"] = previous_datasource.id
    _ensure_metric_values(
        values.get("status"),
        values.get("certification_status"),
        values.get("quality_status"),
    )
    previous_certification_status = metric.certification_status
    previous_certified_by = metric.certified_by
    if "certified_by" in values:
        values["certified_by"] = _validate_metric_certifier(db, values.get("certified_by"), previous_datasource)
    for key, value in values.items():
        setattr(metric, key, value)
    _touch_certification(
        metric,
        current_user,
        previous_status=previous_certification_status,
        previous_certified_by=previous_certified_by,
    )
    db.commit()
    db.refresh(metric)
    current_datasource = (
        db.query(DataSource).filter(DataSource.id == metric.datasource_id).first()
        if metric.datasource_id
        else previous_datasource
    )
    _sync_metric_catalog_asset(db, metric, current_datasource)
    if previous_datasource_id:
        sync_datasource_metrics_prompt(db, previous_datasource_id)
    if metric.datasource_id and metric.datasource_id != previous_datasource_id:
        sync_datasource_metrics_prompt(db, metric.datasource_id)
    elif metric.datasource_id:
        sync_datasource_metrics_prompt(db, metric.datasource_id)
    db.commit()
    db.refresh(metric)
    _record_metric_audit(
        db,
        current_user,
        "metric.update",
        metric,
        org_id=current_datasource.org_id if current_datasource else None,
        message="指标已更新",
        detail={"fields": list(payload.model_dump(exclude_unset=True).keys())},
    )
    return metric


@router.post("/generate-formula")
async def generate_formula(
    payload: MetricCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_admin(current_user)
    _dataset, datasource = _resolve_dataset_binding(db, payload.dataset_id)
    formula = await generate_metric_formula(
        datasource_context={
            "name": datasource.name,
            "metadata_prompt": datasource.metadata_prompt,
            "schema_metadata": datasource.schema_metadata,
        },
        name=payload.name,
        definition=payload.definition,
        column_name=payload.column_name,
    )
    return {"formula": formula}


@router.delete("/{metric_id}")
def delete_metric(
    metric_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_admin(current_user)
    metric = db.query(Metric).filter(Metric.id == metric_id).first()
    if not metric:
        raise HTTPException(status_code=404, detail="指标不存在")
    assert_metric_can_delete(db, metric)
    datasource_id = metric.datasource_id
    metric_id = metric.id
    metric_name = metric.name
    datasource = db.query(DataSource).filter(DataSource.id == datasource_id).first() if datasource_id else None
    _delete_metric_catalog_asset(db, metric_id)
    db.delete(metric)
    db.commit()
    if datasource_id:
        sync_datasource_metrics_prompt(db, datasource_id)
        db.commit()
    _record_metric_audit(
        db,
        current_user,
        "metric.delete",
        None,
        resource_id=metric_id,
        resource_name=metric_name,
        org_id=datasource.org_id if datasource else None,
        message="指标已删除",
    )
    return {"status": "ok"}


@router.post("/{metric_id}/compute")
def compute_metric(
    metric_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Execute the metric SQL and update last_value / last_computed_at."""
    from datetime import datetime
    from sqlalchemy import text
    from app.db.session import get_datasource_engine

    metric = db.query(Metric).filter(Metric.id == metric_id).first()
    if not metric:
        raise HTTPException(status_code=404, detail="指标不存在")

    datasource = db.query(DataSource).filter(DataSource.id == metric.datasource_id).first() if metric.datasource_id else None
    if not datasource:
        raise HTTPException(status_code=400, detail="指标未绑定数据源")

    # Derive main table from the linked dataset's fields_json
    dataset = db.query(Dataset).filter(Dataset.id == metric.dataset_id).first() if metric.dataset_id else None
    fields_json = (dataset.fields_json or {}) if dataset else {}
    table = str(fields_json.get("table") or "").strip()

    formula = (metric.formula or "").strip()

    if formula and table:
        sql = f"SELECT {formula} AS _val FROM {table}"
    elif table and metric.column_name:
        agg = (metric.aggregation or "SUM").upper()
        col = metric.column_name.strip()
        sql = f"SELECT {agg}({col}) AS _val FROM {table}"
    else:
        raise HTTPException(status_code=400, detail="指标缺少计算口径：请配置 column_name 或 formula，并确保数据集已设置主表")

    filters_sql = _render_calculation_filters(metric.calculation_config)
    if filters_sql:
        connector = "AND" if re.search(r"\bwhere\b", sql, flags=re.I) else "WHERE"
        sql = f"{sql} {connector} {filters_sql}"

    try:
        source_type = getattr(datasource, "source_type", "database")
        if source_type == "excel":
            from app.core.excel_executor import execute_excel_query
            from app.core.excel_uploads import resolve_excel_source_path
            file_path = resolve_excel_source_path(datasource.database_url)
            result = execute_excel_query(file_path, sql)
            rows = result.get("rows", [])
            val = float(rows[0][0]) if rows and rows[0][0] is not None else None
        else:
            engine = get_datasource_engine(datasource.database_url)
            with engine.connect() as conn:
                row = conn.execute(text(sql)).fetchone()
            val = float(row[0]) if row and row[0] is not None else None
    except Exception as exc:
        metric.quality_status = "error"
        db.commit()
        raise HTTPException(status_code=500, detail=f"SQL执行失败: {exc}")

    now = datetime.utcnow()
    metric.last_value = val
    metric.last_computed_at = now
    metric.quality_status = "normal"
    metric.data_updated_at = now
    db.commit()
    db.refresh(metric)

    return {"last_value": val, "computed_at": now.isoformat()}
