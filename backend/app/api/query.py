import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, text
from sqlalchemy.orm import Session
from fastapi_cache.decorator import cache

from app.api.auth import get_current_user
from app.core.llm import generate_sql_query, generate_summary, chat, get_llm_config, normalize_llm_config
from app.core.audit import try_record_audit_log
from app.core.metric_binding import match_metric_from_question, sql_uses_metric_formula
from app.core.query_planner import plan_query
from app.core.excel_executor import execute_excel_query
from app.core.sql_guard import detect_excel_join_risk
from app.db.session import get_db, get_datasource_engine
from app.models.datasource import DataSource
from app.models.dataset import Dataset
from app.models.llm_setting import LlmSetting
from app.models.query import QueryHistory
from app.models.user import User
from app.schemas.query import QueryAskRequest, QueryAskResponse, HistoryListResponse
from app.schemas.query import DrillPreviewRequest, DrillPreviewResponse
from app.core.drill_runtime import build_drill_actions
from app.core.drill_suggester import suggest_drill_actions

router = APIRouter(prefix="/query", tags=["query"])


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
    fields = _format_dataset_list(fields_json, "fields")
    filters = _format_dataset_list(dataset.filters_json, "filters")
    derived_columns = _format_dataset_list(dataset.derived_columns_json, "expressions")
    joins = _format_dataset_list(dataset.joins_json, "joins")
    aggregations = _format_dataset_list(dataset.aggregations_json, "aggregations")
    lines = [
        f"当前选择数据集：{dataset.name}",
        "请优先按照这个数据集已经定义好的业务口径生成 SQL。",
        f"主表：{table or '未配置'}",
        f"已选字段：{fields}",
        f"固定筛选：{filters}",
        f"派生列：{derived_columns}",
        f"Join 关系：{joins}",
        f"聚合口径：{aggregations}",
        "如果用户问题没有明确要求跳出数据集范围，不要使用上述数据集未包含的字段或口径。",
    ]
    if dataset.description:
        lines.insert(1, f"数据集说明：{dataset.description}")
    return "\n".join(lines)


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
    mode = payload.mode or "text2sql"
    datasource_id = getattr(payload, "datasource_id", None)
    dataset_id = getattr(payload, "dataset_id", None)
    drill_context = payload.drill_context
    parent_history_id = payload.parent_history_id
    if not question:
        raise HTTPException(status_code=400, detail="问题不能为空")

    dataset = None
    dataset_context = ""
    if dataset_id:
        dataset = _get_dataset_for_user(db, dataset_id, current_user)
        datasource = _get_datasource(db, dataset.datasource_id, current_user)
        dataset_context = _build_dataset_query_context(dataset)
    else:
        datasource = _get_datasource(db, datasource_id, current_user)
    runtime_llm_model = normalize_llm_config(await get_llm_config()).get("model")

    # 闲聊模式
    if mode == "chat":
        try:
            answer = await chat(question)
        except Exception as exc:
            try_record_audit_log(
                db,
                actor=current_user,
                action="query.ask",
                resource_type="query",
                resource_name=datasource.name if datasource else None,
                org_id=datasource.org_id if datasource else current_user.org_id,
                status="error",
                message=f"闲聊失败: {exc}",
                detail={"mode": "chat", "question": question, "llm_model": runtime_llm_model},
            )
            raise HTTPException(status_code=502, detail=f"闲聊失败: {exc}")

        history = QueryHistory(
            user_id=current_user.id,
            datasource_id=datasource.id if datasource else None,
            parent_history_id=parent_history_id,
            question=f"[闲聊] {question}",
            summary=answer,
            mode="chat",
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
            resource_name=datasource.name if datasource else None,
            org_id=datasource.org_id if datasource else current_user.org_id,
            message="智能问数已完成",
            detail={"mode": "chat", "question": question, "llm_model": runtime_llm_model},
        )

        return {
            "answer": answer,
            "result": {"columns": [], "rows": []},
            "summary": "",
            "llm_model": runtime_llm_model,
            "history_id": history.id,
            "recommendations": [],
            "mode": "chat",
        }

    # Text2SQL 模式
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

    history = QueryHistory(
        user_id=current_user.id,
        datasource_id=datasource.id,
        parent_history_id=parent_history_id,
        question=f"[SQL] {question}",
        sql_query=sql_query,
        result_json=json.dumps(result, ensure_ascii=False, default=str),
        summary=summary,
        mode="text2sql",
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
            "mode": "text2sql",
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
        "mode": "text2sql",
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
    if item.result_json:
        try:
            result = json.loads(item.result_json)
        except Exception:
            pass

    return {
        "id": item.id,
        "question": item.question,
        "sql_query": item.sql_query,
        "result": result,
        "summary": item.summary or "",
        "llm_model": item.llm_model or _get_persisted_llm_model(db),
        "mode": item.mode or "text2sql",
        "drill_context": json.loads(item.drill_context) if item.drill_context else None,
        "parent_history_id": item.parent_history_id,
        "created_at": item.created_at.strftime("%Y-%m-%d %H:%M"),
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
