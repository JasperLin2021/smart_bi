import asyncio
import json
import logging
import re
import time
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, inspect, or_, text
from sqlalchemy.orm import Session
from fastapi_cache.decorator import cache
from fastapi.responses import StreamingResponse

from app.api.auth import get_current_user
from app.core.llm import (
    generate_sql_query,
    generate_summary,
    get_llm_config,
    normalize_llm_config,
)
from app.core.agentic_nl2sql import (
    assert_read_only_sql,
    build_agentic_chart_spec,
    build_agentic_nl2sql,
    repair_agentic_sql_after_execution_error,
)
from app.core.audit import try_record_audit_log
from app.core.metric_binding import (
    match_metrics_from_question,
    metric_caliber_formula,
    sql_uses_metric_formula,
    sql_uses_metric_time_field,
)
from app.core.query_planner import plan_query
from app.core.excel_executor import execute_excel_query
from app.core.sql_guard import detect_excel_join_risk
from app.core.semantic_layer import build_semantic_query_plan, execute_semantic_sql, infer_semantic_model
from app.db.session import get_db, get_datasource_engine
from app.models.datasource import DataSource
from app.models.dataset import Dataset
from app.models.llm_setting import LlmSetting
from app.models.metric import Metric
from app.models.query import QueryHistory
from app.models.user import User
from app.schemas.query import QueryAskRequest, QueryAskResponse, HistoryListResponse
from app.schemas.query import SemanticQueryRequest, SemanticQueryResponse
from app.schemas.query import DrillPreviewRequest, DrillPreviewResponse
from app.core.drill_runtime import build_drill_actions
from app.core.drill_suggester import suggest_drill_actions
from app.core.rls_enforcer import get_rls_clauses, apply_rls_to_sql

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/query", tags=["query"])

QUERY_MODES = {"business", "explore", "agentic"}
AGENTIC_ROLES = {"dept_admin", "department_admin", "org_admin", "super_admin"}
AGENTIC_HISTORY_PREFIXES = ("探索模式", "探索问数", "Agentic问数")


def _normalize_query_mode(mode: str | None, dataset_id: int | None = None) -> str:
    normalized = (mode or "business").strip().lower()
    if normalized == "text2sql":
        return "business" if dataset_id else "agentic"
    if normalized == "explore":
        return "agentic"
    if normalized not in QUERY_MODES:
        raise HTTPException(status_code=400, detail="不支持的问数模式，请使用业务问数或探索模式")
    return normalized


def _ensure_query_mode_allowed(mode: str, dataset_id: int | None, current_user: User) -> None:
    if mode == "business" and not dataset_id:
        raise HTTPException(status_code=400, detail="业务问数必须选择数据集")
    if mode == "agentic" and dataset_id:
        raise HTTPException(status_code=400, detail="探索模式只能选择数据源")
    if mode == "agentic" and getattr(current_user, "role", None) not in AGENTIC_ROLES:
        raise HTTPException(status_code=403, detail="探索模式仅部门管理员及以上可用")


def _query_mode_label(mode: str) -> str:
    if mode in {"agentic", "explore"}:
        return "探索模式"
    return "业务问数"


def _normalize_history_mode(mode: str | None) -> str:
    if mode in {"agentic", "explore"}:
        return "agentic"
    return "business"


def _infer_history_mode(item: QueryHistory) -> str:
    if any(item.question.startswith(f"[{prefix}]") for prefix in AGENTIC_HISTORY_PREFIXES):
        return "agentic"
    return _normalize_history_mode(item.mode)


def _history_mode_condition(mode: str | None):
    if not mode:
        return None
    normalized = _normalize_query_mode(mode)
    agentic_prefix_conditions = [
        QueryHistory.question.like(f"[{prefix}]%")
        for prefix in AGENTIC_HISTORY_PREFIXES
    ]
    agentic_condition = or_(
        QueryHistory.mode.in_(["agentic", "explore"]),
        *agentic_prefix_conditions,
    )
    if normalized == "agentic":
        return agentic_condition
    return and_(
        or_(QueryHistory.mode.is_(None), QueryHistory.mode.notin_(["agentic", "explore"])),
        *[~condition for condition in agentic_prefix_conditions],
    )


def _apply_history_mode_filter(query, mode: str | None):
    condition = _history_mode_condition(mode)
    return query.filter(condition) if condition is not None else query


def _root_history_id(item: QueryHistory) -> int:
    return item.parent_history_id or item.id


def _resolve_parent_history_id(
    db: Session,
    parent_history_id: int | None,
    datasource_id: int,
    mode: str,
    current_user: User,
) -> int | None:
    if not parent_history_id:
        return None
    parent = (
        db.query(QueryHistory)
        .filter(QueryHistory.user_id == current_user.id, QueryHistory.id == parent_history_id)
        .first()
    )
    if not parent:
        return None
    if parent.datasource_id != datasource_id:
        return None
    if _normalize_history_mode(parent.mode) != _normalize_history_mode(mode):
        return None
    return _root_history_id(parent)


def _history_result_parts(item: QueryHistory) -> tuple[dict, list, list, dict | None, dict | None, dict | None, dict | None]:
    result = {"columns": [], "rows": []}
    trust_signals = []
    agent_trace = []
    chart_spec = None
    agent_notes = None
    empty_diagnostics = None
    semantic_context = None
    if item.result_json:
        try:
            result = json.loads(item.result_json)
            trust_signals = result.pop("_trust_signals", []) or []
            agent_trace = result.pop("_agent_trace", []) or []
            chart_spec = result.pop("_chart_spec", None)
            agent_notes = result.pop("_agent_notes", None)
            empty_diagnostics = result.pop("_empty_diagnostics", None)
            semantic_context = result.pop("_semantic_context", None)
        except Exception:
            pass
    return result, trust_signals, agent_trace, chart_spec, agent_notes, empty_diagnostics, semantic_context


def _history_detail_payload(item: QueryHistory, db: Session) -> dict:
    result, trust_signals, agent_trace, chart_spec, agent_notes, empty_diagnostics, semantic_context = _history_result_parts(item)
    return {
        "id": item.id,
        "datasource_id": item.datasource_id,
        "question": item.question,
        "sql_query": item.sql_query,
        "result": result,
        "summary": item.summary or "",
        "llm_model": item.llm_model or _get_persisted_llm_model(db),
        "mode": _infer_history_mode(item),
        "agent_trace": agent_trace,
        "chart_spec": chart_spec,
        "agent_notes": agent_notes,
        "empty_diagnostics": empty_diagnostics,
        "semantic_context": semantic_context,
        "drill_context": json.loads(item.drill_context) if item.drill_context else None,
        "parent_history_id": item.parent_history_id,
        "created_at": item.created_at.strftime("%Y-%m-%d %H:%M"),
        "trust_signals": trust_signals,
    }


@router.post("/semantic", response_model=SemanticQueryResponse)
def semantic_query(
    payload: SemanticQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = _get_dataset_for_user(db, payload.dataset_id, current_user)
    datasource = _get_datasource(db, dataset.datasource_id, current_user)
    if not datasource:
        raise HTTPException(status_code=404, detail="数据源不存在")
    try:
        plan = build_semantic_query_plan(dataset, payload, datasource=datasource)
        sql_query = plan.sql
        rls_clauses = get_rls_clauses(db, datasource.id, current_user)
        if rls_clauses:
            sql_query = apply_rls_to_sql(sql_query, rls_clauses)
        result = execute_semantic_sql(datasource, sql_query, plan.params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        try_record_audit_log(
            db,
            actor=current_user,
            action="query.semantic",
            resource_type="dataset",
            resource_id=dataset.id,
            resource_name=dataset.name,
            org_id=dataset.org_id,
            status="error",
            message=f"语义查询失败: {exc}",
        )
        raise HTTPException(status_code=502, detail=f"语义查询失败: {exc}")

    response = {
        "dataset_id": dataset.id,
        "columns": plan.columns,
        "labels": plan.labels,
        "rows": result.get("rows", []),
        "sql_query": sql_query,
    }
    try_record_audit_log(
        db,
        actor=current_user,
        action="query.semantic",
        resource_type="dataset",
        resource_id=dataset.id,
        resource_name=dataset.name,
        org_id=dataset.org_id,
        message="语义查询已完成",
        detail={
            "dimensions": payload.dimensions,
            "metrics": payload.metrics,
            "row_count": len(response["rows"]),
        },
    )
    return response


def _get_persisted_llm_model(db: Session) -> str | None:
    record = db.query(LlmSetting).first()
    if not record:
        return None
    return normalize_llm_config(
        {
            "provider": record.provider,
            "base_url": record.base_url,
            "api_key": record.api_key,
            "model": record.model,
            "temperature": record.temperature,
            "agent_planner_mode": record.agent_planner_mode or "llm_only",
        }
    ).get("model")


def _can_access_org_resource(user: User | None, org_id: int | None) -> bool:
    if user is None or user.role == "super_admin":
        return True
    return org_id == user.org_id


def _get_datasource(db: Session, datasource_id: int | None, user: User | None = None) -> DataSource | None:
    if not datasource_id:
        query = db.query(DataSource).filter(DataSource.is_active == 1)
        if user and user.role != "super_admin":
            query = query.filter(DataSource.org_id == user.org_id)
        return query.first()
    ds = db.query(DataSource).filter(DataSource.id == datasource_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    if not _can_access_org_resource(user, ds.org_id):
        raise HTTPException(status_code=403, detail="无权访问此数据源")
    return ds


def _get_recommendations(datasource: DataSource | None) -> list[str]:
    if not datasource or not datasource.recommend_questions:
        return []
    try:
        recommendations = json.loads(datasource.recommend_questions)
    except (json.JSONDecodeError, TypeError):
        return []
    return recommendations if isinstance(recommendations, list) else []


def _extract_agentic_value_probe_terms(question: str) -> list[str]:
    candidates = re.findall(r"(?<![A-Za-z0-9_-])([A-Za-z][A-Za-z0-9_-]{1,31})(?![A-Za-z0-9_-])", question or "")
    ignored = {
        "top",
        "step",
        "alarm",
        "alarmid",
        "alarm_id",
        "error",
        "error_code",
        "equipment",
        "equipmentid",
        "count",
        "trend",
        "date",
        "time",
        "sumdatetime",
    }
    terms: list[str] = []
    for candidate in candidates:
        lowered = candidate.lower()
        if lowered in ignored or re.fullmatch(r"top\d+", lowered):
            continue
        if "_" in candidate and lowered.endswith(("id", "code", "time", "date")):
            continue
        if candidate.islower() and not any(char.isdigit() for char in candidate):
            continue
        if candidate not in terms:
            terms.append(candidate)
    return terms[:3]


def _safe_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _safe_sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _schema_tables_for_value_probe(datasource: DataSource) -> list[dict[str, list[str]]]:
    raw_schema = getattr(datasource, "schema_metadata", None)
    parsed: dict | None = None
    if isinstance(raw_schema, str) and raw_schema.strip():
        try:
            parsed = json.loads(raw_schema)
        except Exception:
            parsed = None
    elif isinstance(raw_schema, dict):
        parsed = raw_schema
    tables: list[dict[str, list[str]]] = []
    for table in (parsed or {}).get("tables", []) if isinstance(parsed, dict) else []:
        if not isinstance(table, dict):
            continue
        name = str(table.get("name") or "").strip()
        columns = []
        for column in table.get("columns") or []:
            if isinstance(column, dict):
                column_name = str(column.get("name") or "").strip()
            else:
                column_name = str(column or "").strip()
            if column_name:
                columns.append(column_name)
        if name and columns:
            tables.append({"name": name, "columns": columns[:24]})
    if tables:
        return tables[:6]

    metadata = getattr(datasource, "metadata_prompt", "") or ""
    for match in re.finditer(r"([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]{1,800})\)", metadata):
        name = match.group(1).strip()
        columns = [
            item.strip().strip("`\"")
            for item in re.split(r"[,，]", match.group(2))
            if item.strip()
        ]
        if name and columns:
            tables.append({"name": name, "columns": columns[:24]})
    return tables[:6]


def _value_probe_sql(table: str, column: str, term: str) -> str:
    table_ref = _safe_identifier(table)
    column_ref = _safe_identifier(column)
    literal = _safe_sql_literal(term)
    return (
        f"SELECT {literal} AS probe_term, {_safe_sql_literal(table)} AS table_name, "
        f"{_safe_sql_literal(column)} AS column_name, CAST({column_ref} AS VARCHAR) AS matched_value, "
        f"COUNT(*) AS match_count FROM {table_ref} "
        f"WHERE LOWER(CAST({column_ref} AS VARCHAR)) = LOWER({literal}) "
        f"GROUP BY {column_ref} ORDER BY match_count DESC LIMIT 3"
    )


def _sample_probe_sql(table: str, column: str, term: str) -> str:
    table_ref = _safe_identifier(table)
    column_ref = _safe_identifier(column)
    literal = _safe_sql_literal(term)
    return (
        f"SELECT * FROM {table_ref} "
        f"WHERE LOWER(CAST({column_ref} AS VARCHAR)) = LOWER({literal}) "
        "LIMIT 3"
    )


def _format_agentic_value_probe_context(probe: dict | None) -> str:
    if not probe or not probe.get("terms"):
        return ""
    terms = [str(item) for item in probe.get("terms") or []]
    matches = [item for item in probe.get("matches") or [] if isinstance(item, dict)]
    if not matches:
        return f"值探测结果：用户问题中的疑似字段值 {', '.join(terms)} 未在抽样扫描范围内命中。"
    lines = [
        f"值探测结果：用户问题中的疑似字段值包括 {', '.join(terms)}。",
        "生成 SQL 时优先把这些片段理解为字段值过滤条件，不要直接当作字段名。",
    ]
    for match in matches[:8]:
        table = match.get("table")
        column = match.get("column")
        value = match.get("matched_value")
        count = match.get("match_count")
        lines.append(f"- {match.get('term')} 命中 {table}.{column} = {value}，匹配 {count} 条。")
        sample_rows = match.get("sample_rows") if isinstance(match.get("sample_rows"), list) else []
        if sample_rows:
            lines.append(f"  样例记录：{json.dumps(sample_rows[:2], ensure_ascii=False, default=str)}")
    return "\n".join(lines)


async def _append_agentic_value_probe(
    datasource: DataSource,
    question: str,
    agent_trace: list[dict],
    on_trace=None,
) -> tuple[dict | None, str]:
    step_start = time.perf_counter()
    terms = _extract_agentic_value_probe_terms(question)
    if not terms:
        return None, ""
    tables = _schema_tables_for_value_probe(datasource)
    matches: list[dict] = []
    checked = 0
    for term in terms:
        term_found = False
        for table in tables:
            for column in table["columns"]:
                if checked >= 80:
                    break
                checked += 1
                try:
                    result, rows = _execute_datasource_sql(datasource, _value_probe_sql(table["name"], column, term))
                except Exception:
                    continue
                for row in rows[:3]:
                    match_count = row.get("match_count", 0)
                    if not match_count:
                        continue
                    sample_rows: list[dict] = []
                    try:
                        sample_result, sample_rows = _execute_datasource_sql(
                            datasource,
                            _sample_probe_sql(table["name"], column, term),
                        )
                    except Exception:
                        sample_rows = []
                    matches.append(
                        {
                            "term": term,
                            "table": table["name"],
                            "column": column,
                            "matched_value": row.get("matched_value"),
                            "match_count": match_count,
                            "sample_rows": sample_rows[:3],
                        }
                    )
                    term_found = True
                if term_found:
                    break
            if term_found or checked >= 80:
                break
    probe = {"terms": terms, "checked_columns": checked, "matches": matches}
    context = _format_agentic_value_probe_context(probe)
    status = "success" if matches else "warning"
    message = "已根据疑似字段值探测到候选字段" if matches else "未在抽样扫描范围内命中疑似字段值"
    await _append_agent_trace(
        agent_trace,
        {
            "stage": "value_probe",
            "status": status,
            "message": message,
            "duration_ms": _duration_ms(step_start),
            "detail": probe,
        },
        on_trace,
    )
    return probe, context


def _normalize_summary(question: str, result: dict, summary: str) -> str:
    rows = result.get("rows", []) if isinstance(result, dict) else []
    if not rows:
        return summary
    no_data_patterns = [
        "未找到",
        "没有找到",
        "无符合条件",
        "未查询到",
        "查询结果为空",
    ]
    if any(pattern in summary for pattern in no_data_patterns):
        return f"查询返回 {len(rows)} 条记录，请直接查看下方结果表。"
    return summary


def _get_drill_config(datasource: DataSource | None) -> dict | None:
    if not datasource or not datasource.drill_config:
        return None
    try:
        return json.loads(datasource.drill_config)
    except (json.JSONDecodeError, TypeError):
        return None


def _get_dataset_drill_config(dataset: Dataset | None) -> dict | None:
    config = getattr(dataset, "drill_config_json", None)
    return config if isinstance(config, dict) else None


def _get_dataset_for_user(db: Session, dataset_id: int, user: User) -> Dataset:
    query = db.query(Dataset).filter(Dataset.id == dataset_id)
    if user.role != "super_admin":
        query = query.filter(Dataset.org_id == user.org_id)
        if user.role != "org_admin":
            query = query.filter(or_(Dataset.status == "published", Dataset.owner_id == user.id))
    dataset = query.first()
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")
    return dataset


def _format_dataset_list(value: object, key: str) -> str:
    if not isinstance(value, dict):
        return "无"
    items = value.get(key)
    if not isinstance(items, list) or not items:
        return "无"
    return ", ".join(str(item) for item in items)


def _build_dataset_query_context(dataset: Dataset) -> str:
    fields_json = dataset.fields_json if isinstance(dataset.fields_json, dict) else {}
    table = str(fields_json.get("table") or "").strip()
    dimensions = _format_dataset_list(fields_json, "dimensions")
    if dimensions == "无":
        dimensions = _format_dataset_list(fields_json, "fields")
    filters = _format_dataset_list(dataset.filters_json, "filters")
    derived_columns = _format_dataset_list(dataset.derived_columns_json, "expressions")
    joins = _format_dataset_list(dataset.joins_json, "joins")
    aggregations = _format_dataset_list(dataset.aggregations_json, "aggregations")
    if aggregations == "无":
        aggregations = _format_dataset_list(fields_json, "metrics")
    lines = [
        f"当前选择数据集：{dataset.name}",
        "请优先按照这个数据集已经定义好的业务口径生成 SQL。",
        f"主表：{table or '未配置'}",
        f"维度字段：{dimensions}",
        f"固定筛选：{filters}",
        f"派生列：{derived_columns}",
        f"Join 关系：{joins}",
        f"指标口径：{aggregations}",
        "如果用户问题没有明确要求跳出数据集范围，不要使用上述数据集未包含的字段或口径。",
    ]
    if dataset.description:
        lines.insert(1, f"数据集说明：{dataset.description}")
    return "\n".join(lines)


def _metric_trust_signal(metric: Metric) -> dict:
    return {
        "metric_id": metric.id,
        "metric_name": metric.name,
        "definition": metric.definition,
        # 展示完整口径（公式 + 固定筛选），让口径对用户透明
        "formula": metric_caliber_formula(metric),
        "owner_name": metric.owner_name,
        "unit": metric.unit,
        "certification_status": metric.certification_status,
        "certified_by": metric.certified_by,
        "certified_at": metric.certified_at.isoformat() if metric.certified_at else None,
        "caliber_version": metric.caliber_version,
        "data_updated_at": metric.data_updated_at.isoformat() if metric.data_updated_at else None,
        "quality_status": metric.quality_status,
        "quality_message": metric.quality_message,
    }


def _query_metric_trust_signals(
    db: Session,
    datasource: DataSource,
    question: str,
    sql_query: str,
    metric_match: dict | None = None,
) -> list[dict]:
    if hasattr(db, "get_bind") and not inspect(db.get_bind()).has_table("metrics"):
        return []
    metrics = (
        db.query(Metric)
        .filter(
            Metric.datasource_id == datasource.id,
            Metric.is_active == 1,
            Metric.status == "published",
            Metric.certification_status != "deprecated",
        )
        .order_by(Metric.updated_at.desc(), Metric.id.desc())
        .all()
    )
    if metric_match and metric_match.get("name"):
        metrics.sort(key=lambda item: item.name != metric_match["name"])
    signals: list[dict] = []
    seen: set[int] = set()
    for metric in metrics:
        if not metric.formula:
            continue
        # 用完整口径（公式 + 固定筛选）判定 SQL 是否真的遵循指标，
        # 防止 SQL 漏掉指标自带筛选（如 order_status='delivered'）仍被误标为可信信号。
        formula_used = sql_uses_metric_formula(sql_query, metric_caliber_formula(metric))
        if not formula_used:
            continue
        if metric.id in seen:
            continue
        seen.add(metric.id)
        signals.append(_metric_trust_signal(metric))
    return signals


def _business_context_field_column(field: str | None) -> str:
    clean = str(field or "").strip()
    if not clean:
        return ""
    return clean.split(".", 1)[1] if "." in clean else clean


def _business_context_mentions_field(sql_query: str, result: dict, field: str | None, item_id: str | None = None) -> bool:
    columns = {str(column).lower() for column in result.get("columns", []) if column is not None}
    lowered_sql = (sql_query or "").lower()
    candidates = {
        str(field or "").lower(),
        _business_context_field_column(field).lower(),
        str(item_id or "").lower(),
    }
    candidates.discard("")
    for candidate in candidates:
        if candidate in columns:
            return True
        if re.search(rf"(?<![A-Za-z0-9_]){re.escape(candidate)}(?![A-Za-z0-9_])", lowered_sql):
            return True
    return False


def _business_context_metric_formula(metric: dict) -> str:
    aggregation = str(metric.get("aggregation") or "sum").upper()
    field = str(metric.get("field") or "*")
    if aggregation == "COUNT_DISTINCT":
        return f"COUNT(DISTINCT {field})"
    return f"{aggregation}({field})"


def _business_context_metric_from_model(metric: dict, source: str = "dataset") -> dict:
    label = str(metric.get("label") or metric.get("id") or "未命名指标")
    return {
        "id": metric.get("id"),
        "name": label,
        "label": label,
        "field": metric.get("field"),
        "aggregation": metric.get("aggregation"),
        "formula": _business_context_metric_formula(metric),
        "definition": metric.get("description"),
        "certification_status": None,
        "quality_status": None,
        "source": source,
    }


def _business_context_dimension_from_model(dimension: dict, kind: str = "dimension") -> dict:
    return {
        "id": dimension.get("id"),
        "field": dimension.get("field"),
        "label": dimension.get("label") or dimension.get("id") or dimension.get("field"),
        "kind": kind,
        "source": "dataset",
        "granularity": dimension.get("granularity"),
        "description": dimension.get("description"),
    }


def _business_context_filter_label(item: object) -> dict | None:
    if isinstance(item, dict):
        label = str(item.get("label") or item.get("name") or "").strip()
        field = item.get("field") or item.get("column") or item.get("id")
        operator = item.get("operator") or item.get("op") or "="
        value = item.get("value")
        if not label:
            if field and value is not None:
                label = f"{field} {operator} {value}"
            elif field:
                label = str(field)
        if not label:
            return None
        return {
            "label": label,
            "field": field,
            "operator": operator,
            "value": value,
            "source": "dataset",
        }
    label = str(item or "").strip()
    if not label:
        return None
    return {"label": label, "field": None, "operator": None, "value": None, "source": "dataset"}


def _dedupe_business_items(items: list[dict], keys: tuple[str, ...]) -> list[dict]:
    deduped = []
    seen: set[tuple] = set()
    for item in items:
        key = tuple(str(item.get(name) or "").lower() for name in keys)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _build_business_semantic_context(
    dataset: Dataset | None,
    trust_signals: list[dict],
    metric_match: dict | None,
    sql_query: str,
    result: dict,
) -> dict | None:
    if not dataset:
        return None
    try:
        model = infer_semantic_model(dataset)
    except Exception:
        model = {"dimensions": [], "metrics": [], "time_dimensions": [], "synonyms": []}

    model_metrics = [_business_context_metric_from_model(metric) for metric in model.get("metrics", [])]
    model_dimensions = [
        *[_business_context_dimension_from_model(item, "dimension") for item in model.get("dimensions", [])],
        *[_business_context_dimension_from_model(item, "time") for item in model.get("time_dimensions", [])],
    ]

    metrics: list[dict] = []
    for signal in trust_signals:
        metrics.append(
            {
                "id": signal.get("metric_id"),
                "name": signal.get("metric_name"),
                "label": signal.get("metric_name"),
                "field": None,
                "aggregation": None,
                "formula": signal.get("formula"),
                "definition": signal.get("definition"),
                "unit": signal.get("unit"),
                "certification_status": signal.get("certification_status"),
                "quality_status": signal.get("quality_status"),
                "owner_name": signal.get("owner_name"),
                "source": "trusted_metric",
            }
        )

    if metric_match and metric_match.get("name"):
        metrics.append(
            {
                "id": metric_match.get("id"),
                "name": metric_match.get("name"),
                "label": metric_match.get("name"),
                "field": metric_match.get("field"),
                "aggregation": metric_match.get("aggregation"),
                "formula": metric_match.get("formula"),
                "definition": metric_match.get("definition"),
                "certification_status": metric_match.get("certification_status"),
                "quality_status": metric_match.get("quality_status"),
                "source": "metric_match",
            }
        )

    for metric in model.get("metrics", []):
        if _business_context_mentions_field(sql_query, result, metric.get("field"), metric.get("id")):
            metrics.append(_business_context_metric_from_model(metric))

    if not metrics and len(model_metrics) == 1:
        metrics.append(model_metrics[0])

    dimensions = [
        item
        for item in model_dimensions
        if _business_context_mentions_field(sql_query, result, item.get("field"), item.get("id"))
    ]
    if not dimensions:
        dimensions = model_dimensions[:4]

    filters_json = dataset.filters_json if isinstance(dataset.filters_json, dict) else {}
    filters = [
        item
        for item in (_business_context_filter_label(raw) for raw in filters_json.get("filters", []) or [])
        if item
    ]

    return {
        "dataset": {
            "id": dataset.id,
            "name": dataset.name,
            "description": dataset.description,
        },
        "metrics": _dedupe_business_items(metrics, ("name", "formula")),
        "dimensions": _dedupe_business_items(dimensions, ("field", "label")),
        "filters": _dedupe_business_items(filters, ("label",)),
        "time_grain": None,
        "available_metrics": _dedupe_business_items(model_metrics, ("name", "formula")),
        "available_dimensions": _dedupe_business_items(model_dimensions, ("field", "label")),
    }


def _metric_match_log_detail(metric_matches: list[dict]) -> list[dict]:
    """指标命中详情（用于日志排查：命中了哪些指标、得分、认证状态）。"""
    return [
        {
            "id": item.get("id"),
            "name": item.get("name"),
            "match_score": item.get("match_score"),
            "certification_status": item.get("certification_status"),
            "source": item.get("source"),
        }
        for item in metric_matches
    ]


def _metric_caliber_matches(sql_query: str, formula: str | None, time_field: str | None = "") -> bool:
    """口径达标判定：指标公式 + 时间字段同时满足。

    时间字段是"日活/月活/流水"等按时间统计指标的一部分——同样的去重公式，
    用不同时间字段过滤会得到不同结果。公式校验通过不代表时间口径正确。
    """
    if not sql_uses_metric_formula(sql_query, formula):
        return False
    return sql_uses_metric_time_field(sql_query, time_field)


def _metric_caliber_retry_context(primary: dict, formula: str | None, time_field: str | None = "") -> str:
    parts = [
        "上一版 SQL 没有使用目标指标公式（或未完全遵循其口径）。",
        f"目标指标：{primary.get('name', '未命名指标')}",
    ]
    if formula:
        parts.append(f"必须使用的公式：{formula}")
    if time_field:
        parts.append(f"必须使用的时间字段：{time_field}（问题中的日期/时间段过滤必须作用于该字段）")
    parts.append("请严格按该指标口径重写 SQL，不要在其基础上增加变换（如加常量、乘系数、改筛选条件），只输出最终 SQL。")
    return "\n".join(parts)


async def _generate_safe_sql(
    question: str,
    datasource: DataSource,
    query_plan: dict | None = None,
    metric_match: dict | None = None,
    metric_matches: list[dict] | None = None,
    context: str = "",
) -> str:
    candidates = metric_matches if metric_matches else ([metric_match] if metric_match else [])
    primary = candidates[0] if candidates else None
    sql_response = await generate_sql_query(
        question,
        datasource=datasource,
        context=context,
        query_plan=query_plan,
        metric_match=primary,
        metric_matches=candidates,
    )
    sql_query = sql_response.get("sql", "")

    metric_formula = (primary or {}).get("formula")
    metric_time_field = (primary or {}).get("time_field") or ""
    if primary and not _metric_caliber_matches(sql_query, metric_formula, metric_time_field):
        retry_context = _metric_caliber_retry_context(primary, metric_formula, metric_time_field)
        retry_response = await generate_sql_query(
            question,
            datasource=datasource,
            context=f"{context}\n\n{retry_context}" if context else retry_context,
            query_plan=query_plan,
            metric_match=primary,
            metric_matches=candidates,
        )
        retried_sql = retry_response.get("sql", "")
        if not _metric_caliber_matches(retried_sql, metric_formula, metric_time_field):
            formula_ok = sql_uses_metric_formula(retried_sql, metric_formula)
            time_ok = sql_uses_metric_time_field(retried_sql, metric_time_field)
            raise ValueError(
                f"生成结果未使用目标指标公式：{primary.get('name', '未命名指标')}"
                f"（公式达标={formula_ok}，时间字段达标={time_ok}；"
                f"指标时间字段={metric_time_field or '(未配置)'}；生成SQL：{retried_sql}）"
            )
        sql_query = retried_sql

    if datasource.source_type != "excel":
        return sql_query

    risk = detect_excel_join_risk(datasource.database_url, sql_query)
    if not risk:
        return sql_query

    retry_context = (
        "上一版 SQL 被风险检查判定为高风险。\n"
        f"原因：{risk['message']}\n"
        f"改写要求：{risk['hint']}\n"
        "请重写为更稳妥的 SQL，只输出最终 SQL。"
    )
    retry_response = await generate_sql_query(
        question,
        datasource=datasource,
        context=f"{context}\n\n{retry_context}" if context else retry_context,
        query_plan=query_plan,
        metric_match=primary,
        metric_matches=candidates,
    )
    retried_sql = retry_response.get("sql", "")
    if primary and not _metric_caliber_matches(retried_sql, metric_formula, metric_time_field):
        formula_ok = sql_uses_metric_formula(retried_sql, metric_formula)
        time_ok = sql_uses_metric_time_field(retried_sql, metric_time_field)
        raise ValueError(
            f"生成结果未使用目标指标公式：{primary.get('name', '未命名指标')}"
            f"（公式达标={formula_ok}，时间字段达标={time_ok}；"
            f"指标时间字段={metric_time_field or '(未配置)'}；生成SQL：{retried_sql}）"
        )
    retry_risk = detect_excel_join_risk(datasource.database_url, retried_sql)
    if retry_risk:
        raise ValueError(f"检测到高风险JOIN。{retry_risk['message']}")
    return retried_sql


def _execute_datasource_sql(datasource: DataSource, sql_query: str) -> tuple[dict, list[dict]]:
    # Single enforcement chokepoint: every code path that runs SQL against a
    # business datasource goes through here, so read-only validation lives here
    # rather than depending on each caller. LLM-generated SQL is never trusted.
    safe_sql = assert_read_only_sql(sql_query)
    if datasource.source_type == "excel":
        result = execute_excel_query(datasource.database_url, safe_sql)
        return result, result["rows"]

    ds_engine = get_datasource_engine(datasource.database_url)
    with ds_engine.connect() as conn:
        result_proxy = conn.execute(text(safe_sql))
        columns = list(result_proxy.keys())
        rows = [dict(row._mapping) for row in result_proxy.fetchall()]
        return {"columns": columns, "rows": rows}, rows


def _format_exception(exc: Exception) -> str:
    message = str(exc).strip()
    return message or exc.__class__.__name__


def _duration_ms(start: float) -> float:
    return round(max(0.0, (time.perf_counter() - start) * 1000), 2)


def _format_agentic_generation_error(exc: Exception, llm_config: dict | None = None) -> str:
    message = _format_exception(exc)
    if isinstance(exc, httpx.ReadTimeout):
        config = llm_config or {}
        model = config.get("model") or "未配置模型"
        base_url = config.get("base_url") or "未配置"
        return f"探索模式底层大模型响应超时: {model} 服务 {base_url} 未在配置的等待时间内返回 ({message})"
    if isinstance(exc, httpx.RequestError):
        config = llm_config or {}
        model = config.get("model") or "未配置模型"
        base_url = config.get("base_url") or "未配置"
        return f"探索模式底层大模型连接失败: 无法连接 {model} 服务 {base_url} ({message})"
    return message


def _resolve_agentic_llm_config(runtime_llm_config: dict) -> tuple[dict, str | None]:
    config = normalize_llm_config(runtime_llm_config)
    return config, config.get("model")


async def _append_agent_trace(agent_trace: list[dict], item: dict, on_trace=None) -> None:
    if "duration_ms" not in item:
        item["duration_ms"] = 0
    agent_trace.append(item)
    if on_trace:
        await on_trace(item)


async def _execute_agentic_sql_with_repair(
    question: str,
    datasource: DataSource,
    sql_query: str,
    query_plan: dict,
    agent_trace: list[dict],
    llm_model: str | None = None,
    llm_config: dict | None = None,
    metric_matches: list[dict] | None = None,
    rls_clauses: list | None = None,
    max_execution_repairs: int = 2,
    on_trace=None,
) -> tuple[str, dict, list[dict]]:
    candidate_sql = sql_query
    for attempt in range(max_execution_repairs + 1):
        step_start = time.perf_counter()
        executable_sql = apply_rls_to_sql(candidate_sql, rls_clauses) if rls_clauses else candidate_sql
        try:
            result, rows = _execute_datasource_sql(datasource, executable_sql)
            trace_item = {
                "stage": "execute",
                "status": "success",
                "message": f"已执行查询，返回 {len(rows)} 条记录",
                "duration_ms": _duration_ms(step_start),
                "detail": {"attempt": attempt + 1, "sql": executable_sql},
            }
            await _append_agent_trace(agent_trace, trace_item, on_trace)
            return executable_sql, result, rows
        except Exception as exc:
            can_retry = attempt < max_execution_repairs
            execution_error = _format_exception(exc)
            trace_item = {
                "stage": "execute",
                "status": "error",
                "message": "SQL 执行失败，已回传错误给 Agent 修复" if can_retry else "SQL 执行失败，已达到最大修复次数",
                "duration_ms": _duration_ms(step_start),
                "detail": {
                    "attempt": attempt + 1,
                    "sql": executable_sql,
                    "generated_sql": candidate_sql,
                    "error": execution_error,
                },
            }
            await _append_agent_trace(agent_trace, trace_item, on_trace)
            if not can_retry:
                raise
            repair_started = {
                "stage": "sql_execute_fix",
                "status": "pending",
                "message": "正在根据执行错误修复 SQL",
                "duration_ms": 0,
                "detail": {
                    "attempt": attempt + 1,
                    "failed_sql": candidate_sql,
                    "execution_error": execution_error,
                },
            }
            await _append_agent_trace(agent_trace, repair_started, on_trace)
            repair_start = time.perf_counter()
            try:
                repaired = await repair_agentic_sql_after_execution_error(
                    question,
                    datasource,
                    query_plan,
                    candidate_sql,
                    execution_error,
                    llm_model=llm_model,
                    llm_config=llm_config,
                    metric_matches=metric_matches,
                    on_trace=on_trace,
                )
            except Exception as repair_exc:
                repair_error = _format_exception(repair_exc)
                repair_failed = {
                    "stage": "sql_execute_fix",
                    "status": "error",
                    "message": f"SQL 修复失败: {repair_error}",
                    "duration_ms": _duration_ms(repair_start),
                    "detail": {
                        "attempt": attempt + 1,
                        "failed_sql": candidate_sql,
                        "execution_error": execution_error,
                        "error": repair_error,
                        "error_type": repair_exc.__class__.__name__,
                    },
                }
                await _append_agent_trace(agent_trace, repair_failed, on_trace)
                raise RuntimeError(f"SQL 修复失败: {repair_error}") from repair_exc
            agent_trace.extend(repaired.get("trace") or [])
            candidate_sql = repaired["sql_query"]

    raise RuntimeError("探索模式 SQL 执行重试失败")


async def _build_agentic_chart_spec_with_trace(
    question: str,
    result: dict,
    agent_trace: list[dict],
    llm_model: str | None = None,
    llm_config: dict | None = None,
    on_trace=None,
) -> dict | None:
    planned = await build_agentic_chart_spec(
        question,
        result,
        llm_model=llm_model,
        llm_config=llm_config,
        on_trace=on_trace,
    )
    trace = planned.get("trace") or []
    if trace:
        agent_trace.extend(trace)
    return planned.get("chart_spec")


def _build_query_execution_error_detail(
    mode: str,
    message: str,
    sql_query: str,
    agent_trace: list[dict],
    llm_model: str | None,
) -> str | dict:
    if mode != "agentic":
        return message
    return {
        "message": message,
        "sql_query": sql_query,
        "agent_trace": agent_trace,
        "llm_model": llm_model,
    }


def _build_agentic_stream_unhandled_error_detail(
    exc: Exception,
    sql_query: str,
    agent_trace: list[dict],
    llm_model: str | None,
) -> dict:
    message = f"流式问数失败: {_format_exception(exc)}"
    finalize_trace = {
        "stage": "stream_finalize",
        "status": "error",
        "message": message,
        "duration_ms": 0,
        "detail": {
            "error": _format_exception(exc),
            "error_type": exc.__class__.__name__,
            "sql": sql_query,
        },
    }
    return {
        "message": message,
        "sql_query": sql_query,
        "agent_trace": [*agent_trace, finalize_trace],
        "llm_model": llm_model,
    }


def _refinement_action(label: str, question: str) -> dict:
    return {"label": label, "question": question.strip()}


def _build_agentic_empty_diagnostics(question: str, sql_query: str, result: dict) -> dict:
    columns = result.get("columns", []) if isinstance(result, dict) else []
    checks = ["SQL 执行成功但返回 0 行"]
    if columns:
        checks.append(f"结果列已返回：{', '.join(str(column) for column in columns[:6])}")
    lower_question = question.lower()
    lower_sql = sql_query.lower()
    has_time_condition = any(token in lower_question or token in lower_sql for token in ("最近", "近", "天", "周", "月", "date", "time", "interval", "between"))
    has_filter_condition = " where " in f" {lower_sql} "
    if has_time_condition:
        checks.append("查询包含时间范围，空结果可能由时间窗口过窄导致")
    if has_filter_condition:
        checks.append("查询包含筛选条件，空结果可能由字段值或条件组合过窄导致")
    if not has_time_condition and not has_filter_condition:
        checks.append("查询未命中数据，建议先查看主表数据量和可用字段值")

    suggested_actions = [
        _refinement_action("放宽时间范围", f"{question}，放宽时间范围后重新查询，优先查看最近90天或全量可用时间"),
        _refinement_action("移除部分筛选", f"{question}，先移除非必要筛选条件，查看是否存在匹配数据"),
        _refinement_action("查看可用字段值", f"基于当前数据源，先查看和这个问题相关字段的可用取值与数据分布：{question}"),
        _refinement_action("重新分析条件", f"重新分析这个问题的查询条件，先判断哪些条件可能导致空结果，再生成更稳妥的查询：{question}"),
    ]
    return {
        "reason": "no_matching_rows",
        "checks": checks,
        "suggested_actions": suggested_actions,
    }


async def _append_agentic_empty_diagnostics(
    question: str,
    sql_query: str,
    result: dict,
    agent_trace: list[dict],
    on_trace=None,
) -> dict:
    step_start = time.perf_counter()
    diagnostics = _build_agentic_empty_diagnostics(question, sql_query, result)
    await _append_agent_trace(
        agent_trace,
        {
            "stage": "empty_diagnostics",
            "status": "warning",
            "message": "查询结果为空，已生成排查建议",
            "duration_ms": _duration_ms(step_start),
            "detail": diagnostics,
        },
        on_trace,
    )
    return diagnostics


def _sse_event(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"


@router.post("/ask", response_model=QueryAskResponse)
@cache(expire=60)
async def ask(
    payload: QueryAskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    question = payload.question.strip()
    mode = payload.mode or "business"
    datasource_id = getattr(payload, "datasource_id", None)
    dataset_id = getattr(payload, "dataset_id", None)
    drill_context = payload.drill_context
    if not question:
        raise HTTPException(status_code=400, detail="问题不能为空")

    mode = _normalize_query_mode(mode, dataset_id)
    _ensure_query_mode_allowed(mode, dataset_id, current_user)

    dataset = None
    dataset_context = ""
    if dataset_id:
        dataset = _get_dataset_for_user(db, dataset_id, current_user)
        datasource = _get_datasource(db, dataset.datasource_id, current_user)
        dataset_context = _build_dataset_query_context(dataset)
    else:
        datasource = _get_datasource(db, datasource_id, current_user)
    runtime_llm_config = normalize_llm_config(await get_llm_config())
    agentic_llm_config, agentic_llm_model = (
        _resolve_agentic_llm_config(runtime_llm_config) if mode == "agentic" else (None, None)
    )
    runtime_llm_model = agentic_llm_model if mode == "agentic" else runtime_llm_config.get("model")

    # 问数模式
    if not datasource:
        raise HTTPException(status_code=400, detail="请先选择或配置数据源")
    parent_history_id = _resolve_parent_history_id(db, payload.parent_history_id, datasource.id, mode, current_user)

    agent_trace: list[dict] = []
    agent_notes = None
    value_probe_context = ""
    try:
        if mode == "agentic":
            metric_matches = match_metrics_from_question(db, question, datasource)
            logger.info(
                "探索模式指标命中 question=%r datasource_id=%s matched=%s",
                question[:150],
                datasource.id,
                json.dumps(_metric_match_log_detail(metric_matches), ensure_ascii=False),
            )
            _, value_probe_context = await _append_agentic_value_probe(
                datasource,
                question,
                agent_trace,
            )
            agentic_result = await build_agentic_nl2sql(
                question,
                datasource,
                llm_model=runtime_llm_model,
                llm_config=agentic_llm_config,
                extra_context=value_probe_context,
                metric_matches=metric_matches,
            )
            query_plan = agentic_result.get("plan") or {}
            metric_match = metric_matches[0] if metric_matches else None
            sql_query = agentic_result["sql_query"]
            agent_trace.extend(agentic_result.get("trace") or [])
            agent_notes = agentic_result.get("agent_notes")
        else:
            query_plan = await plan_query(question, datasource)
            metric_matches = match_metrics_from_question(
                db,
                question,
                datasource,
                dataset_id=dataset.id if dataset else None,
            )
            logger.info(
                "业务问数指标命中 question=%r datasource_id=%s dataset_id=%s matched=%s",
                question[:150],
                datasource.id,
                dataset.id if dataset else None,
                json.dumps(_metric_match_log_detail(metric_matches), ensure_ascii=False),
            )
            metric_match = metric_matches[0] if metric_matches else None
            sql_query = await _generate_safe_sql(
                question,
                datasource,
                query_plan,
                metric_match=metric_match,
                metric_matches=metric_matches,
                context=dataset_context,
            )
    except Exception as exc:
        generation_error = (
            _format_agentic_generation_error(exc, agentic_llm_config)
            if mode == "agentic"
            else _format_exception(exc)
        )
        error_message = f"SQL生成失败: {generation_error}"
        try_record_audit_log(
            db,
            actor=current_user,
            action="query.ask",
            resource_type="query",
            resource_name=datasource.name,
            org_id=datasource.org_id,
            status="error",
            message=error_message,
            detail={
                "stage": "generate_sql",
                "question": question,
                "datasource_id": datasource.id,
                "dataset_id": dataset.id if dataset else None,
                "llm_model": runtime_llm_model,
            },
        )
        raise HTTPException(status_code=502, detail=error_message)

    # Execute SQL based on source type
    # Apply Row-Level Security rules before execution
    rls_clauses = get_rls_clauses(db, datasource.id, current_user)
    if mode != "agentic" and rls_clauses:
        sql_query = apply_rls_to_sql(sql_query, rls_clauses)

    result = {"columns": [], "rows": []}
    rows = []
    chart_spec = None
    empty_diagnostics = None
    try:
        if mode == "agentic":
            sql_query, result, rows = await _execute_agentic_sql_with_repair(
                question,
                datasource,
                sql_query,
                query_plan,
                agent_trace,
                llm_model=runtime_llm_model,
                llm_config=agentic_llm_config,
                metric_matches=metric_matches,
                rls_clauses=rls_clauses,
            )
        else:
            result, rows = _execute_datasource_sql(datasource, sql_query)
    except Exception as exc:
        error_message = f"SQL执行失败: {exc}"
        try_record_audit_log(
            db,
            actor=current_user,
            action="query.ask",
            resource_type="query",
            resource_name=datasource.name,
            org_id=datasource.org_id,
            status="error",
            message=error_message,
            detail={
                "stage": "execute_sql",
                "question": question,
                "datasource_id": datasource.id,
                "dataset_id": dataset.id if dataset else None,
                "llm_model": runtime_llm_model,
            },
        )
        raise HTTPException(
            status_code=502,
            detail=_build_query_execution_error_detail(
                mode,
                error_message,
                sql_query,
                agent_trace,
                runtime_llm_model,
            ),
        )

    if mode == "agentic" and rows:
        chart_spec = await _build_agentic_chart_spec_with_trace(
            question,
            result,
            agent_trace,
            llm_model=runtime_llm_model,
            llm_config=agentic_llm_config,
        )
    elif mode == "agentic":
        empty_diagnostics = await _append_agentic_empty_diagnostics(
            question,
            sql_query,
            result,
            agent_trace,
        )

    # 生成摘要
    try:
        summary = await generate_summary(question, result, chart_spec=chart_spec) if mode == "agentic" else await generate_summary(question, result)
    except Exception:
        summary = "分析总结生成失败，请查看图表和明细数据。"
    if mode != "agentic":
        summary = _normalize_summary(question, result, summary)

    recommendations = _get_recommendations(datasource)
    trust_signals = _query_metric_trust_signals(db, datasource, question, sql_query, metric_match)
    semantic_context = _build_business_semantic_context(
        dataset,
        trust_signals,
        metric_match,
        sql_query,
        result,
    )
    stored_result = {
        **result,
        "_trust_signals": trust_signals,
        "_semantic_context": semantic_context,
        "_agent_trace": agent_trace,
        "_chart_spec": chart_spec,
        "_agent_notes": agent_notes,
        "_empty_diagnostics": empty_diagnostics,
    }

    history = QueryHistory(
        user_id=current_user.id,
        datasource_id=datasource.id,
        parent_history_id=parent_history_id,
        question=f"[{_query_mode_label(mode)}] {question}",
        sql_query=sql_query,
        result_json=json.dumps(stored_result, ensure_ascii=False, default=str),
        summary=summary,
        mode=mode,
        drill_context=json.dumps(drill_context, ensure_ascii=False) if drill_context else None,
        llm_model=runtime_llm_model,
    )
    db.add(history)
    db.commit()
    db.refresh(history)
    try_record_audit_log(
        db,
        actor=current_user,
        action="query.ask",
        resource_type="query",
        resource_id=history.id,
        resource_name=datasource.name,
        org_id=datasource.org_id,
        message="智能问数已完成",
        detail={
            "mode": mode,
            "question": question,
            "datasource_id": datasource.id,
            "dataset_id": dataset.id if dataset else None,
            "llm_model": runtime_llm_model,
            "row_count": len(rows),
        },
    )

    return {
        "answer": "已生成并执行查询。",
        "result": result,
        "summary": summary,
        "sql_query": sql_query,
        "llm_model": runtime_llm_model,
        "history_id": history.id,
        "recommendations": recommendations,
        "mode": mode,
        "trust_signals": trust_signals,
        "semantic_context": semantic_context,
        "agent_trace": agent_trace,
        "chart_spec": chart_spec,
        "agent_notes": agent_notes,
        "empty_diagnostics": empty_diagnostics,
    }


@router.post("/ask-stream")
async def ask_stream(
    payload: QueryAskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="问题不能为空")

    mode = _normalize_query_mode(payload.mode or "business", payload.dataset_id)
    if mode != "agentic":
        raise HTTPException(status_code=400, detail="流式问数仅支持探索模式")
    _ensure_query_mode_allowed(mode, payload.dataset_id, current_user)

    datasource = _get_datasource(db, payload.datasource_id, current_user)
    if not datasource:
        raise HTTPException(status_code=400, detail="请先选择或配置数据源")
    parent_history_id = _resolve_parent_history_id(db, payload.parent_history_id, datasource.id, mode, current_user)

    runtime_llm_config = normalize_llm_config(await get_llm_config())
    agentic_llm_config, runtime_llm_model = _resolve_agentic_llm_config(runtime_llm_config)

    async def event_stream():
        queue: asyncio.Queue[tuple[str, dict] | None] = asyncio.Queue()
        agent_trace: list[dict] = []
        sql_query = ""
        query_plan: dict = {}
        metric_match = None
        result = {"columns": [], "rows": []}
        rows: list[dict] = []
        chart_spec = None
        agent_notes = None
        empty_diagnostics = None
        value_probe_context = ""

        async def emit_trace(item: dict):
            await queue.put(("trace", item))

        async def run_query():
            nonlocal sql_query, query_plan, metric_match, result, rows, chart_spec, agent_notes, empty_diagnostics, value_probe_context
            try:
                metric_matches = match_metrics_from_question(db, question, datasource)
                _, value_probe_context = await _append_agentic_value_probe(
                    datasource,
                    question,
                    agent_trace,
                    on_trace=emit_trace,
                )
                agentic_result = await build_agentic_nl2sql(
                    question,
                    datasource,
                    llm_model=runtime_llm_model,
                    llm_config=agentic_llm_config,
                    extra_context=value_probe_context,
                    metric_matches=metric_matches,
                    on_trace=emit_trace,
                )
                query_plan = agentic_result.get("plan") or {}
                metric_match = metric_matches[0] if metric_matches else None
                sql_query = agentic_result["sql_query"]
                agent_trace.extend(agentic_result.get("trace") or [])
                agent_notes = agentic_result.get("agent_notes")
            except Exception as exc:
                message = f"SQL生成失败: {_format_agentic_generation_error(exc, agentic_llm_config)}"
                try_record_audit_log(
                    db,
                    actor=current_user,
                    action="query.ask",
                    resource_type="query",
                    resource_name=datasource.name,
                    org_id=datasource.org_id,
                    status="error",
                    message=message,
                    detail={
                        "stage": "generate_sql",
                        "question": question,
                        "datasource_id": datasource.id,
                        "dataset_id": None,
                        "llm_model": runtime_llm_model,
                    },
                )
                await queue.put(("error", {"message": message, "agent_trace": agent_trace, "llm_model": runtime_llm_model}))
                return

            rls_clauses = get_rls_clauses(db, datasource.id, current_user)
            try:
                sql_query, result, rows = await _execute_agentic_sql_with_repair(
                    question,
                    datasource,
                    sql_query,
                    query_plan,
                    agent_trace,
                    llm_model=runtime_llm_model,
                    llm_config=agentic_llm_config,
                    metric_matches=metric_matches,
                    rls_clauses=rls_clauses,
                    on_trace=emit_trace,
                )
            except Exception as exc:
                error_message = f"SQL执行失败: {exc}"
                try_record_audit_log(
                    db,
                    actor=current_user,
                    action="query.ask",
                    resource_type="query",
                    resource_name=datasource.name,
                    org_id=datasource.org_id,
                    status="error",
                    message=error_message,
                    detail={
                        "stage": "execute_sql",
                        "question": question,
                        "datasource_id": datasource.id,
                        "dataset_id": None,
                        "llm_model": runtime_llm_model,
                    },
                )
                await queue.put(
                    (
                        "error",
                        _build_query_execution_error_detail(
                            mode,
                            error_message,
                            sql_query,
                            agent_trace,
                            runtime_llm_model,
                        ),
                    )
                )
                return

            if rows:
                chart_spec = await _build_agentic_chart_spec_with_trace(
                    question,
                    result,
                    agent_trace,
                    llm_model=runtime_llm_model,
                    llm_config=agentic_llm_config,
                    on_trace=emit_trace,
                )
            else:
                empty_diagnostics = await _append_agentic_empty_diagnostics(
                    question,
                    sql_query,
                    result,
                    agent_trace,
                    on_trace=emit_trace,
                )

            try:
                summary = await generate_summary(question, result, chart_spec=chart_spec)
            except Exception:
                summary = "分析总结生成失败，请查看图表和明细数据。"

            recommendations = _get_recommendations(datasource)
            trust_signals = _query_metric_trust_signals(db, datasource, question, sql_query, metric_match)
            stored_result = {
                **result,
                "_trust_signals": trust_signals,
                "_semantic_context": None,
                "_agent_trace": agent_trace,
                "_chart_spec": chart_spec,
                "_agent_notes": agent_notes,
                "_empty_diagnostics": empty_diagnostics,
            }
            history = QueryHistory(
                user_id=current_user.id,
                datasource_id=datasource.id,
                parent_history_id=parent_history_id,
                question=f"[{_query_mode_label(mode)}] {question}",
                sql_query=sql_query,
                result_json=json.dumps(stored_result, ensure_ascii=False, default=str),
                summary=summary,
                mode=mode,
                drill_context=json.dumps(payload.drill_context, ensure_ascii=False) if payload.drill_context else None,
                llm_model=runtime_llm_model,
            )
            db.add(history)
            db.commit()
            db.refresh(history)
            try_record_audit_log(
                db,
                actor=current_user,
                action="query.ask",
                resource_type="query",
                resource_id=history.id,
                resource_name=datasource.name,
                org_id=datasource.org_id,
                message="智能问数已完成",
                detail={
                    "mode": mode,
                    "question": question,
                    "datasource_id": datasource.id,
                    "dataset_id": None,
                    "llm_model": runtime_llm_model,
                    "row_count": len(rows),
                },
            )
            await queue.put(
                (
                    "final",
                    {
                        "answer": "已生成并执行查询。",
                        "result": result,
                        "summary": summary,
                        "sql_query": sql_query,
                        "llm_model": runtime_llm_model,
                        "history_id": history.id,
                        "recommendations": recommendations,
                        "mode": mode,
                        "trust_signals": trust_signals,
                        "semantic_context": None,
                        "agent_trace": agent_trace,
                        "chart_spec": chart_spec,
                        "agent_notes": agent_notes,
                        "empty_diagnostics": empty_diagnostics,
                    },
                )
            )

        async def producer():
            try:
                await run_query()
            except Exception as exc:
                db.rollback()
                detail = _build_agentic_stream_unhandled_error_detail(
                    exc,
                    sql_query,
                    agent_trace,
                    runtime_llm_model,
                )
                try_record_audit_log(
                    db,
                    actor=current_user,
                    action="query.ask",
                    resource_type="query",
                    resource_name=datasource.name,
                    org_id=datasource.org_id,
                    status="error",
                    message=detail["message"],
                    detail={
                        "stage": "stream_finalize",
                        "question": question,
                        "datasource_id": datasource.id,
                        "dataset_id": None,
                        "llm_model": runtime_llm_model,
                        "sql_query": sql_query,
                    },
                )
                await queue.put(("error", detail))
            finally:
                await queue.put(None)

        task = asyncio.create_task(producer())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                event, data = item
                yield _sse_event(event, data)
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/history", response_model=HistoryListResponse)
def history(
    datasource_id: int | None = None,
    mode: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(QueryHistory).filter(QueryHistory.user_id == current_user.id)
    if datasource_id:
        query = query.filter(QueryHistory.datasource_id == datasource_id)
    query = _apply_history_mode_filter(query, mode)
    rows = query.order_by(QueryHistory.created_at.desc()).limit(200).all()

    grouped: dict[int, list[QueryHistory]] = {}
    missing_root_ids: set[int] = set()
    row_ids = {row.id for row in rows}
    for row in rows:
        root_id = _root_history_id(row)
        grouped.setdefault(root_id, []).append(row)
        if root_id != row.id and root_id not in row_ids:
            missing_root_ids.add(root_id)

    if missing_root_ids:
        root_query = db.query(QueryHistory).filter(
            QueryHistory.user_id == current_user.id,
            QueryHistory.id.in_(missing_root_ids),
        )
        if datasource_id:
            root_query = root_query.filter(QueryHistory.datasource_id == datasource_id)
        root_query = _apply_history_mode_filter(root_query, mode)
        for root in root_query.all():
            grouped.setdefault(root.id, []).append(root)

    conversation_items: list[tuple[QueryHistory, QueryHistory]] = []
    for root_id, group in grouped.items():
        root = next((item for item in group if item.id == root_id), None)
        if not root:
            continue
        latest = max(group, key=lambda item: (item.created_at, item.id))
        conversation_items.append((root, latest))

    conversation_items.sort(key=lambda pair: (pair[1].created_at, pair[1].id), reverse=True)
    items = conversation_items[:50]
    return {
        "items": [
            {
                "id": root.id,
                "question": root.question,
                "created_at": latest.created_at.strftime("%Y-%m-%d %H:%M"),
                "favorite": root.favorite,
                "mode": _infer_history_mode(root),
                "parent_history_id": root.parent_history_id,
            }
            for root, latest in items
        ]
    }


@router.post("/history/{history_id}/favorite")
def toggle_favorite(
    history_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = (
        db.query(QueryHistory)
        .filter(QueryHistory.id == history_id, QueryHistory.user_id == current_user.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="记录不存在")
    item.favorite = not item.favorite
    db.commit()
    return {"status": "ok"}


@router.delete("/history/{history_id}")
def delete_history(
    history_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = (
        db.query(QueryHistory)
        .filter(QueryHistory.id == history_id, QueryHistory.user_id == current_user.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="记录不存在")
    delete_items = [item]
    if item.parent_history_id is None:
        delete_items.extend(
            db.query(QueryHistory)
            .filter(QueryHistory.user_id == current_user.id, QueryHistory.parent_history_id == item.id)
            .all()
        )
    for delete_item in delete_items:
        db.delete(delete_item)
    db.commit()
    return {"status": "ok"}


@router.delete("/history")
def delete_all_history(
    datasource_id: int | None = None,
    mode: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(QueryHistory).filter(QueryHistory.user_id == current_user.id)
    if datasource_id:
        query = query.filter(QueryHistory.datasource_id == datasource_id)
    query = _apply_history_mode_filter(query, mode)
    deleted = query.delete(synchronize_session=False)
    db.commit()
    return {"status": "ok", "deleted": deleted}


@router.get("/history/{history_id}")
def get_history_detail(
    history_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = (
        db.query(QueryHistory)
        .filter(QueryHistory.id == history_id, QueryHistory.user_id == current_user.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="记录不存在")

    root_id = _root_history_id(item)
    conversation = (
        db.query(QueryHistory)
        .filter(
            QueryHistory.user_id == current_user.id,
            or_(QueryHistory.id == root_id, QueryHistory.parent_history_id == root_id),
        )
        .order_by(QueryHistory.created_at.asc(), QueryHistory.id.asc())
        .all()
    )
    detail = _history_detail_payload(item, db)
    detail["conversation"] = [_history_detail_payload(turn, db) for turn in conversation]
    return detail


@router.post("/drill-preview", response_model=DrillPreviewResponse)
async def drill_preview(
    payload: DrillPreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    datasource = _get_datasource(db, payload.datasource_id, current_user)
    if not datasource:
        raise HTTPException(status_code=404, detail="数据源不存在")

    dataset = None
    if payload.dataset_id:
        dataset = _get_dataset_for_user(db, payload.dataset_id, current_user)
        if dataset.datasource_id != datasource.id:
            raise HTTPException(status_code=400, detail="数据集与数据源不匹配")

    config = _get_dataset_drill_config(dataset) or _get_drill_config(datasource)
    config_actions = build_drill_actions(config, payload.columns, payload.row) if config else []
    if config_actions:
        return {"actions": config_actions, "detail_action": None}

    del db, current_user, datasource, dataset
    preview = {"actions": [], "detail_action": None}
    try:
        preview = await suggest_drill_actions(
            question=payload.question,
            sql_query=payload.sql_query,
            columns=payload.columns,
            row=payload.row,
            selected_column=payload.selected_column,
        )
    except Exception:
        preview = {"actions": [], "detail_action": None}
    return preview


class SaveInsightRequest(BaseModel):
    history_id: int
    title: str


@router.post("/save-insight")
def save_insight(
    payload: SaveInsightRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = db.query(QueryHistory).filter(QueryHistory.id == payload.history_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="历史记录不存在")
    if record.user_id != current_user.id and current_user.role != "super_admin":
        raise HTTPException(status_code=403, detail="无权操作")
    record.is_insight = True
    record.insight_title = payload.title
    record.org_id = current_user.org_id
    db.commit()
    return {"status": "ok", "history_id": record.id}


@router.delete("/save-insight/{history_id}")
def remove_insight(
    history_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = db.query(QueryHistory).filter(QueryHistory.id == history_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="历史记录不存在")
    if record.user_id != current_user.id and current_user.role != "super_admin":
        raise HTTPException(status_code=403, detail="无权操作")
    record.is_insight = False
    record.insight_title = None
    db.commit()
    return {"status": "ok"}


@router.get("/insights")
def list_insights(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(QueryHistory).filter(QueryHistory.is_insight == True)  # noqa: E712
    if current_user.role != "super_admin":
        q = q.filter(QueryHistory.org_id == current_user.org_id)
    items = q.order_by(QueryHistory.created_at.desc()).limit(limit).all()
    return [
        {
            "id": r.id,
            "title": r.insight_title or r.question,
            "question": r.question,
            "sql_query": r.sql_query,
            "summary": r.summary,
            "created_at": r.created_at,
            "user_id": r.user_id,
        }
        for r in items
    ]
