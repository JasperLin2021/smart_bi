import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi_cache.decorator import cache

from app.api.auth import get_current_user
from app.core.llm import generate_sql_query, generate_summary, chat
from app.db.session import get_db, get_datasource_engine
from app.models.datasource import DataSource
from app.models.query import QueryHistory
from app.models.user import User
from app.schemas.query import QueryAskRequest, QueryAskResponse, HistoryListResponse

router = APIRouter(prefix="/query", tags=["query"])


def _get_datasource(db: Session, datasource_id: int | None) -> DataSource | None:
    if not datasource_id:
        return db.query(DataSource).filter(DataSource.is_active == 1).first()
    ds = db.query(DataSource).filter(DataSource.id == datasource_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    return ds


def _get_recommendations(datasource: DataSource | None) -> list[str]:
    if not datasource or not datasource.recommend_questions:
        return []
    try:
        return json.loads(datasource.recommend_questions)
    except (json.JSONDecodeError, TypeError):
        return []


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
    if not question:
        raise HTTPException(status_code=400, detail="问题不能为空")

    datasource = _get_datasource(db, datasource_id)

    # 闲聊模式
    if mode == "chat":
        try:
            answer = await chat(question)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"闲聊失败: {exc}")

        history = QueryHistory(
            user_id=current_user.id,
            datasource_id=datasource.id if datasource else None,
            question=f"[闲聊] {question}",
            summary=answer,
            mode="chat",
        )
        db.add(history)
        db.commit()

        return {
            "answer": answer,
            "result": {"columns": [], "rows": []},
            "summary": "",
            "recommendations": [],
            "mode": "chat",
        }

    # Text2SQL 模式
    if not datasource:
        raise HTTPException(status_code=400, detail="请先选择或配置数据源")

    try:
        sql_response = await generate_sql_query(question, datasource=datasource)
        sql_query = sql_response.get("sql", "")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"SQL生成失败: {exc}")

    # 使用数据源的数据库连接执行SQL
    result = {"columns": [], "rows": []}
    rows = []
    try:
        ds_engine = get_datasource_engine(datasource.database_url)
        with ds_engine.connect() as conn:
            result_proxy = conn.execute(text(sql_query))
            columns = list(result_proxy.keys())
            rows = [dict(row._mapping) for row in result_proxy.fetchall()]
            result = {"columns": columns, "rows": rows}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"SQL执行失败: {exc}")

    # 生成摘要
    try:
        summary = await generate_summary(question, result)
    except Exception:
        summary = f"已生成SQL查询结果，共{len(rows)}条记录。"

    recommendations = _get_recommendations(datasource)

    history = QueryHistory(
        user_id=current_user.id,
        datasource_id=datasource.id,
        question=f"[SQL] {question}",
        sql_query=sql_query,
        result_json=json.dumps(result, ensure_ascii=False, default=str),
        summary=summary,
        mode="text2sql",
    )
    db.add(history)
    db.commit()

    return {
        "answer": "已生成并执行查询。",
        "result": result,
        "summary": summary,
        "sql_query": sql_query,
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
        "mode": item.mode or "text2sql",
        "created_at": item.created_at.strftime("%Y-%m-%d %H:%M"),
    }
