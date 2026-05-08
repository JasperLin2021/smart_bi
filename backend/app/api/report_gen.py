"""Natural-language report generation using LLM."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.llm import chat_completion
from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.pinned_chart import PinnedChart
from app.models.user import User
from app.api.pinned_charts import _execute_chart_sql, _get_chart_datasource

router = APIRouter(prefix="/report-gen", tags=["report-gen"])

_REPORT_SYSTEM_PROMPT = """你是一名资深数据分析师，请根据提供的图表数据撰写一份结构化的数据分析报告。

报告要求：
1. 使用标准 Markdown 格式输出
2. 包含以下章节（如有数据支撑）：
   - ## 核心结论（1-3条，直接点明最重要发现）
   - ## 数据详情（关键数值说明，不要罗列全部数据）
   - ## 趋势与规律（如有时间维度）
   - ## 建议（可选，基于数据给出行动建议）
3. 语言简洁，每条结论不超过50字
4. 数字保留1位小数，并注明单位（如已知）
5. 输出只包含 Markdown 正文，不要有代码块包裹"""


class ReportRequest(BaseModel):
    chart_id: int | None = None
    title: str = ""
    question: str = ""
    columns: list[str] = []
    rows: list[dict] = []
    datasource_id: int | None = None


class ReportResponse(BaseModel):
    markdown: str
    title: str


@router.post("", response_model=ReportResponse)
async def generate_report(
    payload: ReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    del current_user

    title = payload.title
    columns = payload.columns
    rows = payload.rows

    if payload.chart_id:
        chart = db.query(PinnedChart).filter(PinnedChart.id == payload.chart_id).first()
        if not chart:
            raise HTTPException(status_code=404, detail="图表不存在")
        title = title or chart.title
        ds = _get_chart_datasource(db, chart.datasource_id)
        if not ds:
            raise HTTPException(status_code=400, detail="数据源不存在")
        try:
            result = _execute_chart_sql(ds, chart.sql_query)
            columns = result["columns"]
            rows = result["rows"]
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"数据获取失败: {exc}")

    if not rows:
        raise HTTPException(status_code=400, detail="没有数据可供分析")

    # Summarize data for the prompt (limit to 50 rows to avoid token limits)
    sample_rows = rows[:50]
    data_summary = f"列名: {columns}\n数据（前{len(sample_rows)}行）:\n"
    for row in sample_rows:
        data_summary += str(row) + "\n"

    question_hint = f"问题/指标: {payload.question}\n" if payload.question else ""

    messages = [
        {"role": "system", "content": _REPORT_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"图表名称: {title}\n"
                f"{question_hint}"
                f"总行数: {len(rows)}\n"
                f"{data_summary}"
            ),
        },
    ]

    try:
        markdown = await chat_completion(messages, temperature=0.5)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM调用失败: {exc}")

    return ReportResponse(markdown=markdown.strip(), title=title or "数据分析报告")
