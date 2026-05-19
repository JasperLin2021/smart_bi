import asyncio
import json
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import inspect, or_, text
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
    AgenticClarificationRequired,
    build_agentic_chart_spec,
    build_agentic_nl2sql,
    repair_agentic_sql_after_execution_error,
)
from app.core.audit import try_record_audit_log
from app.core.metric_binding import match_metric_from_question, sql_uses_metric_formula
from app.core.query_planner import plan_query
from app.core.excel_executor import execute_excel_query
from app.core.sql_guard import detect_excel_join_risk
from app.core.semantic_layer import build_semantic_query_plan, execute_semantic_sql
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

router = APIRouter(prefix="/query", tags=["query"])

QUERY_MODES = {"business", "explore", "agentic"}
AGENTIC_ROLES = {"dept_admin", "department_admin", "org_admin", "super_admin"}


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
        plan = build_semantic_query_plan(dataset, payload)
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


def _format_clarification_message(questions: list[str]) -> str:
    if not questions:
        questions = [
            "你想分析哪个指标或字段？",
            "是否需要限定时间范围、维度或筛选条件？",
        ]
    question_lines = "\n".join(f"{index}. {question}" for index, question in enumerate(questions, start=1))
    return f"这个问题还不够明确，我需要先确认一下再查询：\n{question_lines}"


def _build_agentic_clarification_payload(
    exc: AgenticClarificationRequired,
    runtime_llm_model: str | None,
    datasource: DataSource | None = None,
) -> dict:
    message = _format_clarification_message(exc.questions)
    return {
        "answer": message,
        "result": {"columns": [], "rows": []},
        "summary": message,
        "sql_query": None,
        "llm_model": runtime_llm_model,
        "history_id": None,
        "recommendations": _get_recommendations(datasource),
        "mode": "agentic",
        "trust_signals": [],
        "agent_trace": exc.trace,
        "chart_spec": None,
    }


def _agentic_empty_result_confirmation(question: str, result: dict, sql_query: str) -> str:
    columns = result.get("columns", []) if isinstance(result, dict) else []
    column_text = f"返回字段：{', '.join(str(column) for column in columns)}。" if columns else ""
    return (
        "查询已执行，但没有返回数据。"
        "这可能是正常的，也可能是时间范围、筛选条件、字段口径或数据源选择过窄导致的。"
        f"{column_text}"
        "请确认：时间范围是否正确、筛选条件是否过严、是否使用了正确的数据源和字段口径。"
        "如果这些条件无误，可以告诉我新的时间范围或筛选条件，我再继续查询。"
    )


def _agentic_empty_result_trace(sql_query: str, result: dict) -> dict | None:
    rows = result.get("rows", []) if isinstance(result, dict) else []
    if rows:
        return None
    return {
        "stage": "result_check",
        "status": "warning",
        "message": "查询结果为空，建议向用户确认筛选条件",
        "detail": {
            "row_count": 0,
            "columns": result.get("columns", []) if isinstance(result, dict) else [],
            "sql": sql_query,
            "suggestions": [
                "确认时间范围是否过窄",
                "确认筛选条件是否过严",
                "确认数据源和字段口径是否匹配问题",
            ],
        },
    }


def _get_drill_config(datasource: DataSource | None) -> dict | None:
    if not datasource or not datasource.drill_config:
        return None
    try:
        return json.loads(datasource.drill_config)
    except (json.JSONDecodeError, TypeError):
        return None


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
        "formula": metric.formula,
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
        formula_used = sql_uses_metric_formula(sql_query, metric.formula)
        if not formula_used:
            continue
        if metric.id in seen:
            continue
        seen.add(metric.id)
        signals.append(_metric_trust_signal(metric))
    return signals


async def _generate_safe_sql(
    question: str,
    datasource: DataSource,
    query_plan: dict | None = None,
    metric_match: dict | None = None,
    context: str = "",
) -> str:
    sql_response = await generate_sql_query(
        question,
        datasource=datasource,
        context=context,
        query_plan=query_plan,
        metric_match=metric_match,
    )
    sql_query = sql_response.get("sql", "")

    metric_formula = (metric_match or {}).get("formula")
    if metric_match and not sql_uses_metric_formula(sql_query, metric_formula):
        retry_context = (
            "上一版 SQL 没有使用目标指标公式。\n"
            f"目标指标：{metric_match.get('name', '未命名指标')}\n"
            f"必须使用的公式：{metric_formula}\n"
            "请严格按该指标口径重写 SQL，只输出最终 SQL。"
        )
        retry_response = await generate_sql_query(
            question,
            datasource=datasource,
            context=f"{context}\n\n{retry_context}" if context else retry_context,
            query_plan=query_plan,
            metric_match=metric_match,
        )
        retried_sql = retry_response.get("sql", "")
        if not sql_uses_metric_formula(retried_sql, metric_formula):
            raise ValueError(f"生成结果未使用目标指标公式：{metric_match.get('name', '未命名指标')}")
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
        metric_match=metric_match,
    )
    retried_sql = retry_response.get("sql", "")
    if metric_match and not sql_uses_metric_formula(retried_sql, metric_formula):
        raise ValueError(f"生成结果未使用目标指标公式：{metric_match.get('name', '未命名指标')}")
    retry_risk = detect_excel_join_risk(datasource.database_url, retried_sql)
    if retry_risk:
        raise ValueError(f"检测到高风险JOIN。{retry_risk['message']}")
    return retried_sql


def _execute_datasource_sql(datasource: DataSource, sql_query: str) -> tuple[dict, list[dict]]:
    if datasource.source_type == "excel":
        result = execute_excel_query(datasource.database_url, sql_query)
        return result, result["rows"]

    ds_engine = get_datasource_engine(datasource.database_url)
    with ds_engine.connect() as conn:
        result_proxy = conn.execute(text(sql_query))
        columns = list(result_proxy.keys())
        rows = [dict(row._mapping) for row in result_proxy.fetchall()]
        return {"columns": columns, "rows": rows}, rows


def _format_exception(exc: Exception) -> str:
    message = str(exc).strip()
    return message or exc.__class__.__name__


def _format_agentic_generation_error(exc: Exception, llm_config: dict | None = None) -> str:
    message = _format_exception(exc)
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
    rls_clauses: list | None = None,
    max_execution_repairs: int = 2,
    on_trace=None,
) -> tuple[str, dict, list[dict]]:
    candidate_sql = sql_query
    for attempt in range(max_execution_repairs + 1):
        executable_sql = apply_rls_to_sql(candidate_sql, rls_clauses) if rls_clauses else candidate_sql
        try:
            result, rows = _execute_datasource_sql(datasource, executable_sql)
            trace_item = {
                "stage": "execute",
                "status": "success",
                "message": f"已执行查询，返回 {len(rows)} 条记录",
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
                "detail": {
                    "attempt": attempt + 1,
                    "failed_sql": candidate_sql,
                    "execution_error": execution_error,
                },
            }
            await _append_agent_trace(agent_trace, repair_started, on_trace)
            try:
                repaired = await repair_agentic_sql_after_execution_error(
                    question,
                    datasource,
                    query_plan,
                    candidate_sql,
                    execution_error,
                    llm_model=llm_model,
                    llm_config=llm_config,
                    on_trace=on_trace,
                )
            except Exception as repair_exc:
                repair_error = _format_exception(repair_exc)
                repair_failed = {
                    "stage": "sql_execute_fix",
                    "status": "error",
                    "message": f"SQL 修复失败: {repair_error}",
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
    parent_history_id = payload.parent_history_id
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

    agent_trace: list[dict] = []
    try:
        if mode == "agentic":
            agentic_result = await build_agentic_nl2sql(
                question,
                datasource,
                llm_model=runtime_llm_model,
                llm_config=agentic_llm_config,
            )
            query_plan = agentic_result.get("plan") or {}
            metric_match = match_metric_from_question(question, datasource)
            sql_query = agentic_result["sql_query"]
            agent_trace = agentic_result.get("trace") or []
        else:
            query_plan = await plan_query(question, datasource)
            metric_match = match_metric_from_question(question, datasource)
            sql_query = await _generate_safe_sql(
                question,
                datasource,
                query_plan,
                metric_match=metric_match,
                context=dataset_context,
            )
    except AgenticClarificationRequired as exc:
        agent_trace = exc.trace
        try_record_audit_log(
            db,
            actor=current_user,
            action="query.ask",
            resource_type="query",
            resource_name=datasource.name,
            org_id=datasource.org_id,
            message="探索模式需要澄清",
            detail={
                "stage": "clarify",
                "question": question,
                "datasource_id": datasource.id,
                "llm_model": runtime_llm_model,
                "questions": exc.questions,
            },
        )
        return _build_agentic_clarification_payload(exc, runtime_llm_model, datasource)
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

    if mode == "agentic":
        empty_trace = _agentic_empty_result_trace(sql_query, result)
        if empty_trace:
            agent_trace.append(empty_trace)
        elif rows:
            chart_spec = await _build_agentic_chart_spec_with_trace(
                question,
                result,
                agent_trace,
                llm_model=runtime_llm_model,
                llm_config=agentic_llm_config,
            )

    # 生成摘要
    empty_result_message = _agentic_empty_result_confirmation(question, result, sql_query) if mode == "agentic" and not rows else ""
    if empty_result_message:
        summary = empty_result_message
    else:
        try:
            summary = await generate_summary(question, result)
        except Exception:
            summary = f"已生成SQL查询结果，共{len(rows)}条记录。"
        summary = _normalize_summary(question, result, summary)

    recommendations = _get_recommendations(datasource)
    trust_signals = _query_metric_trust_signals(db, datasource, question, sql_query, metric_match)
    stored_result = {**result, "_trust_signals": trust_signals, "_agent_trace": agent_trace, "_chart_spec": chart_spec}

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
        "answer": empty_result_message or "已生成并执行查询。",
        "result": result,
        "summary": summary,
        "sql_query": sql_query,
        "llm_model": runtime_llm_model,
        "history_id": history.id,
        "recommendations": recommendations,
        "mode": mode,
        "trust_signals": trust_signals,
        "agent_trace": agent_trace,
        "chart_spec": chart_spec,
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

        async def emit_trace(item: dict):
            await queue.put(("trace", item))

        async def run_query():
            nonlocal sql_query, query_plan, metric_match, result, rows, chart_spec
            try:
                agentic_result = await build_agentic_nl2sql(
                    question,
                    datasource,
                    llm_model=runtime_llm_model,
                    llm_config=agentic_llm_config,
                    on_trace=emit_trace,
                )
                query_plan = agentic_result.get("plan") or {}
                metric_match = match_metric_from_question(question, datasource)
                sql_query = agentic_result["sql_query"]
                agent_trace[:] = agentic_result.get("trace") or []
            except AgenticClarificationRequired as exc:
                agent_trace[:] = exc.trace
                try_record_audit_log(
                    db,
                    actor=current_user,
                    action="query.ask",
                    resource_type="query",
                    resource_name=datasource.name,
                    org_id=datasource.org_id,
                    message="探索模式需要澄清",
                    detail={
                        "stage": "clarify",
                        "question": question,
                        "datasource_id": datasource.id,
                        "dataset_id": None,
                        "llm_model": runtime_llm_model,
                        "questions": exc.questions,
                    },
                )
                await queue.put(("final", _build_agentic_clarification_payload(exc, runtime_llm_model, datasource)))
                return
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

            empty_trace = _agentic_empty_result_trace(sql_query, result)
            if empty_trace:
                agent_trace.append(empty_trace)
                await emit_trace(empty_trace)

            chart_spec = await _build_agentic_chart_spec_with_trace(
                question,
                result,
                agent_trace,
                llm_model=runtime_llm_model,
                llm_config=agentic_llm_config,
                on_trace=emit_trace,
            ) if rows else None

            empty_result_message = _agentic_empty_result_confirmation(question, result, sql_query) if not rows else ""
            if empty_result_message:
                summary = empty_result_message
            else:
                try:
                    summary = await generate_summary(question, result)
                except Exception:
                    summary = f"已生成SQL查询结果，共{len(rows)}条记录。"
                summary = _normalize_summary(question, result, summary)

            recommendations = _get_recommendations(datasource)
            trust_signals = _query_metric_trust_signals(db, datasource, question, sql_query, metric_match)
            stored_result = {**result, "_trust_signals": trust_signals, "_agent_trace": agent_trace, "_chart_spec": chart_spec}
            history = QueryHistory(
                user_id=current_user.id,
                datasource_id=datasource.id,
                parent_history_id=payload.parent_history_id,
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
                        "answer": empty_result_message or "已生成并执行查询。",
                        "result": result,
                        "summary": summary,
                        "sql_query": sql_query,
                        "llm_model": runtime_llm_model,
                        "history_id": history.id,
                        "recommendations": recommendations,
                        "mode": mode,
                        "trust_signals": trust_signals,
                        "agent_trace": agent_trace,
                        "chart_spec": chart_spec,
                    },
                )
            )

        async def producer():
            try:
                await run_query()
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(QueryHistory).filter(QueryHistory.user_id == current_user.id)
    if datasource_id:
        query = query.filter(QueryHistory.datasource_id == datasource_id)
    items = query.order_by(QueryHistory.created_at.desc()).limit(50).all()
    return {
        "items": [
            {
                "id": item.id,
                "question": item.question,
                "created_at": item.created_at.strftime("%Y-%m-%d"),
                "favorite": item.favorite,
                "parent_history_id": item.parent_history_id,
            }
            for item in items
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
    db.delete(item)
    db.commit()
    return {"status": "ok"}


@router.delete("/history")
def delete_all_history(
    datasource_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(QueryHistory).filter(QueryHistory.user_id == current_user.id)
    if datasource_id:
        query = query.filter(QueryHistory.datasource_id == datasource_id)
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

    result = {"columns": [], "rows": []}
    trust_signals = []
    agent_trace = []
    chart_spec = None
    if item.result_json:
        try:
            result = json.loads(item.result_json)
            trust_signals = result.pop("_trust_signals", []) or []
            agent_trace = result.pop("_agent_trace", []) or []
            chart_spec = result.pop("_chart_spec", None)
        except Exception:
            pass

    return {
        "id": item.id,
        "question": item.question,
        "sql_query": item.sql_query,
        "result": result,
        "summary": item.summary or "",
        "llm_model": item.llm_model or _get_persisted_llm_model(db),
        "mode": _normalize_history_mode(item.mode),
        "agent_trace": agent_trace,
        "chart_spec": chart_spec,
        "drill_context": json.loads(item.drill_context) if item.drill_context else None,
        "parent_history_id": item.parent_history_id,
        "created_at": item.created_at.strftime("%Y-%m-%d %H:%M"),
        "trust_signals": trust_signals,
    }


@router.post("/drill-preview", response_model=DrillPreviewResponse)
async def drill_preview(
    payload: DrillPreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    datasource = _get_datasource(db, payload.datasource_id, current_user)
    if not datasource:
        raise HTTPException(status_code=404, detail="数据源不存在")

    del db, current_user, datasource
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
