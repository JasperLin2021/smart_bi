import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import inspect, or_, text
from sqlalchemy.orm import Session
from fastapi_cache.decorator import cache

from app.api.auth import get_current_user
from app.core.llm import generate_sql_query, generate_summary, get_llm_config, normalize_llm_config
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

QUERY_MODES = {"business", "explore"}
EXPLORE_ROLES = {"dept_admin", "department_admin", "org_admin", "super_admin"}


def _normalize_query_mode(mode: str | None, dataset_id: int | None = None) -> str:
    normalized = (mode or "business").strip().lower()
    if normalized == "text2sql":
        return "business" if dataset_id else "explore"
    if normalized not in QUERY_MODES:
        raise HTTPException(status_code=400, detail="不支持的问数模式，请使用业务问数或探索模式")
    return normalized


def _ensure_query_mode_allowed(mode: str, dataset_id: int | None, current_user: User) -> None:
    if mode == "business" and not dataset_id:
        raise HTTPException(status_code=400, detail="业务问数必须选择数据集")
    if mode == "explore" and getattr(current_user, "role", None) not in EXPLORE_ROLES:
        raise HTTPException(status_code=403, detail="探索模式仅部门管理员及以上可用")


def _query_mode_label(mode: str) -> str:
    return "探索问数" if mode == "explore" else "业务问数"


def _normalize_history_mode(mode: str | None) -> str:
    if mode == "explore":
        return "explore"
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
        .filter(Metric.datasource_id == datasource.id, Metric.is_active == 1)
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
    runtime_llm_model = normalize_llm_config(await get_llm_config()).get("model")

    # 问数模式
    if not datasource:
        raise HTTPException(status_code=400, detail="请先选择或配置数据源")

    try:
        query_plan = await plan_query(question, datasource)
        metric_match = match_metric_from_question(question, datasource)
        sql_query = await _generate_safe_sql(
            question,
            datasource,
            query_plan,
            metric_match=metric_match,
            context=dataset_context,
        )
    except Exception as exc:
        try_record_audit_log(
            db,
            actor=current_user,
            action="query.ask",
            resource_type="query",
            resource_name=datasource.name,
            org_id=datasource.org_id,
            status="error",
            message=f"SQL生成失败: {exc}",
            detail={
                "stage": "generate_sql",
                "question": question,
                "datasource_id": datasource.id,
                "dataset_id": dataset.id if dataset else None,
                "llm_model": runtime_llm_model,
            },
        )
        raise HTTPException(status_code=502, detail=f"SQL生成失败: {exc}")

    # Execute SQL based on source type
    # Apply Row-Level Security rules before execution
    rls_clauses = get_rls_clauses(db, datasource.id, current_user)
    if rls_clauses:
        sql_query = apply_rls_to_sql(sql_query, rls_clauses)

    result = {"columns": [], "rows": []}
    rows = []
    try:
        if datasource.source_type == "excel":
            result = execute_excel_query(datasource.database_url, sql_query)
            rows = result["rows"]
        else:
            ds_engine = get_datasource_engine(datasource.database_url)
            with ds_engine.connect() as conn:
                result_proxy = conn.execute(text(sql_query))
                columns = list(result_proxy.keys())
                rows = [dict(row._mapping) for row in result_proxy.fetchall()]
                result = {"columns": columns, "rows": rows}
    except Exception as exc:
        try_record_audit_log(
            db,
            actor=current_user,
            action="query.ask",
            resource_type="query",
            resource_name=datasource.name,
            org_id=datasource.org_id,
            status="error",
            message=f"SQL执行失败: {exc}",
            detail={
                "stage": "execute_sql",
                "question": question,
                "datasource_id": datasource.id,
                "dataset_id": dataset.id if dataset else None,
                "llm_model": runtime_llm_model,
            },
        )
        raise HTTPException(status_code=502, detail=f"SQL执行失败: {exc}")

    # 生成摘要
    try:
        summary = await generate_summary(question, result)
    except Exception:
        summary = f"已生成SQL查询结果，共{len(rows)}条记录。"
    summary = _normalize_summary(question, result, summary)

    recommendations = _get_recommendations(datasource)
    trust_signals = _query_metric_trust_signals(db, datasource, question, sql_query, metric_match)
    stored_result = {**result, "_trust_signals": trust_signals}

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
    }


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
    if item.result_json:
        try:
            result = json.loads(item.result_json)
            trust_signals = result.pop("_trust_signals", []) or []
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
