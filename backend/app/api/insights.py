import json
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.llm import chat_completion, get_llm_config, normalize_llm_config
from app.db.session import get_db
from app.models.datasource import DataSource
from app.models.metric import Metric
from app.models.organization import Organization  # noqa: F401 - register relationship target for SQLAlchemy
from app.models.user import User

router = APIRouter(prefix="/insights", tags=["insights"])


class MetricExplainRequest(BaseModel):
    metric_id: int
    question: str | None = None


class ChartRecommendRequest(BaseModel):
    columns: list[str]
    rows: list[dict] = []


class AutoInsightsRequest(BaseModel):
    columns: list[str]
    rows: list[dict] = []
    question: str | None = None
    sql_query: str | None = None
    max_items: int = 6


class AnomalyAttributionRequest(BaseModel):
    columns: list[str]
    rows: list[dict] = []
    question: str | None = None
    sql_query: str | None = None
    metric_column: str | None = None
    dimension_columns: list[str] = []
    max_drivers: int = 5


def _to_number(value) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _numeric_columns(columns: list[str], rows: list[dict]) -> list[str]:
    numeric: list[str] = []
    for column in columns:
        values = [_to_number(row.get(column)) for row in rows]
        available = [value for value in values if value is not None]
        if available and len(available) >= max(1, len(rows) // 2):
            numeric.append(column)
    return numeric


def _dimension_columns(columns: list[str], rows: list[dict], numeric_columns: list[str]) -> list[str]:
    numeric_set = set(numeric_columns)
    candidates = [column for column in columns if column not in numeric_set]
    return [column for column in candidates if len({str(row.get(column, "")) for row in rows}) <= max(20, len(rows))]


def _time_column(columns: list[str]) -> str | None:
    keywords = ("date", "time", "day", "month", "year", "日期", "时间", "月份", "年度")
    return next((column for column in columns if any(keyword in column.lower() for keyword in keywords)), None)


def _label_for_row(row: dict, columns: list[str], metric_column: str) -> str:
    for column in columns:
        if column != metric_column and row.get(column) not in (None, ""):
            return str(row.get(column))
    return "当前记录"


def _extract_json_object(raw: str) -> dict:
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


def _compact_rows(rows: list[dict], limit: int = 20) -> list[dict]:
    compacted: list[dict] = []
    for row in rows[:limit]:
        compacted.append({key: row.get(key) for key in row.keys()})
    return compacted


def _valid_insight(item: dict) -> dict | None:
    if not isinstance(item, dict):
        return None
    title = str(item.get("title") or "").strip()
    description = str(item.get("description") or "").strip()
    if not title or not description:
        return None
    severity = str(item.get("severity") or "info").strip()
    if severity not in {"info", "success", "warning", "danger"}:
        severity = "info"
    return {
        "type": str(item.get("type") or "business"),
        "title": title,
        "description": description,
        "severity": severity,
    }


async def _call_insight_llm(payload: dict, task: str) -> tuple[dict, dict]:
    config = normalize_llm_config(await get_llm_config())
    raw = await chat_completion(
        [
            {
                "role": "system",
                "content": (
                    "你是企业 BI 分析助手。只基于传入的统计证据生成业务解释，"
                    "不得编造不存在的数值、字段、时间范围或业务背景。"
                    "必须返回严格 JSON，不要输出 Markdown。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"任务：{task}\n"
                    "请用中文生成面向业务用户的解释层。"
                    "保留证据中的关键数值，不要重新计算。"
                    f"\n输入：{json.dumps(payload, ensure_ascii=False, default=str)}"
                ),
            },
        ],
        temperature=0.2,
        config_override=config,
    )
    return _extract_json_object(raw), config


async def _enhance_auto_insights_with_llm(payload: AutoInsightsRequest, result: dict, rows: list[dict]) -> dict:
    result.setdefault("metadata", {})
    result["metadata"].update({"llm_enhanced": False, "llm_model": None})
    if not rows:
        return result
    try:
        llm_result, config = await _call_insight_llm(
            {
                "question": payload.question,
                "sql_query": payload.sql_query,
                "columns": payload.columns,
                "sample_rows": _compact_rows(rows),
                "rule_insights": result.get("insights", []),
                "metadata": result.get("metadata", {}),
                "required_schema": {
                    "summary": "string",
                    "insights": [
                        {
                            "type": "string",
                            "title": "string",
                            "description": "string",
                            "severity": "info|success|warning|danger",
                        }
                    ],
                },
            },
            "润色自动洞察，输出 summary 和 insights。insights 最多保留用户请求的条数。",
        )
        summary = str(llm_result.get("summary") or "").strip()
        insights = [
            insight
            for insight in (_valid_insight(item) for item in llm_result.get("insights", []))
            if insight
        ]
        if summary:
            result["summary"] = summary
        if insights:
            result["insights"] = insights[: max(1, payload.max_items)]
        result["metadata"].update({"llm_enhanced": bool(summary or insights), "llm_model": config.get("model")})
    except Exception as exc:
        result["metadata"]["llm_error"] = str(exc)
    return result


async def _enhance_attribution_with_llm(payload: AnomalyAttributionRequest, result: dict, rows: list[dict]) -> dict:
    result.update({"llm_enhanced": False, "llm_model": None})
    if not rows or not result.get("drivers"):
        return result
    try:
        llm_result, config = await _call_insight_llm(
            {
                "question": payload.question,
                "sql_query": payload.sql_query,
                "columns": payload.columns,
                "sample_rows": _compact_rows(rows),
                "metric_column": result.get("metric_column"),
                "drivers": result.get("drivers", []),
                "summary": result.get("summary"),
                "recommendations": result.get("recommendations", []),
                "required_schema": {
                    "summary": "string",
                    "recommendations": ["string"],
                },
            },
            "基于已计算好的归因 drivers 生成业务解释和后续建议。不得修改 drivers 数值。",
        )
        summary = str(llm_result.get("summary") or "").strip()
        recommendations = [
            str(item).strip()
            for item in llm_result.get("recommendations", [])
            if str(item).strip()
        ]
        if summary:
            result["summary"] = summary
        if recommendations:
            result["recommendations"] = recommendations[:5]
        result.update({"llm_enhanced": bool(summary or recommendations), "llm_model": config.get("model")})
    except Exception as exc:
        result["llm_error"] = str(exc)
    return result


def _metric_for_user(db: Session, metric_id: int, user: User) -> tuple[Metric, DataSource | None]:
    metric = db.query(Metric).filter(Metric.id == metric_id).first()
    if not metric:
        raise HTTPException(status_code=404, detail="指标不存在")
    datasource = db.query(DataSource).filter(DataSource.id == metric.datasource_id).first()
    if user.role != "super_admin" and datasource and datasource.org_id != user.org_id:
        raise HTTPException(status_code=403, detail="无权访问此指标")
    return metric, datasource


@router.post("/explain-metric")
def explain_metric(
    payload: MetricExplainRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    metric, datasource = _metric_for_user(db, payload.metric_id, current_user)
    parts = [f"{metric.name} 的业务口径是：{metric.definition}"]
    if metric.formula:
        parts.append(f"计算公式：{metric.formula}")
    if metric.unit:
        parts.append(f"单位：{metric.unit}")
    if metric.dimensions:
        parts.append(f"建议分析维度：{', '.join(metric.dimensions)}")
    if datasource:
        parts.append(f"来源数据源：{datasource.name}")
    return {
        "metric_id": metric.id,
        "summary": "；".join(parts),
        "formula": metric.formula,
        "dimensions": metric.dimensions or [],
        "tags": metric.tags or [],
    }


@router.post("/recommend-chart")
def recommend_chart(
    payload: ChartRecommendRequest,
    current_user: User = Depends(get_current_user),
):
    del current_user
    columns = [column.lower() for column in payload.columns]
    row_count = len(payload.rows)
    if row_count == 1 and len(columns) <= 3:
        chart_type = "kpi"
    elif any(word in " ".join(columns) for word in ["date", "time", "month", "day", "year"]):
        chart_type = "line"
    elif len(columns) >= 2 and row_count <= 8:
        chart_type = "pie"
    elif len(columns) >= 2:
        chart_type = "bar"
    else:
        chart_type = "table"
    return {
        "chart_type": chart_type,
        "reason": "根据字段数量、时间字段和返回行数自动推荐。",
    }


@router.post("/auto-insights")
async def auto_insights(
    payload: AutoInsightsRequest,
    current_user: User = Depends(get_current_user),
):
    del current_user
    rows = payload.rows[:1000]
    numeric_columns = _numeric_columns(payload.columns, rows)
    if not rows:
        return {
            "insights": [],
            "summary": "暂无可分析数据",
            "metadata": {"row_count": 0, "numeric_columns": [], "llm_enhanced": False, "llm_model": None},
        }
    if not numeric_columns:
        result = {
            "insights": [
                {
                    "type": "structure",
                    "title": "返回明细数据",
                    "description": f"本次返回 {len(rows)} 行，字段以文本或分类字段为主。",
                    "severity": "info",
                }
            ],
            "summary": "当前结果更适合明细查看或按分类字段继续筛选。",
            "metadata": {"row_count": len(rows), "numeric_columns": []},
        }
        return await _enhance_auto_insights_with_llm(payload, result, rows)

    insights: list[dict] = []
    main_metric = numeric_columns[0]
    values = [(_to_number(row.get(main_metric)), row) for row in rows]
    values = [(value, row) for value, row in values if value is not None]
    total = sum(value for value, _ in values)
    average = total / len(values) if values else 0
    top_value, top_row = max(values, key=lambda item: item[0])
    low_value, low_row = min(values, key=lambda item: item[0])
    insights.append(
        {
            "type": "summary",
            "title": f"{main_metric} 合计 {round(total, 2)}",
            "description": f"共 {len(rows)} 行数据，平均值 {round(average, 2)}。",
            "severity": "info",
        }
    )
    insights.append(
        {
            "type": "top_driver",
            "title": f"{_label_for_row(top_row, payload.columns, main_metric)} 贡献最高",
            "description": f"{main_metric} 为 {round(top_value, 2)}，是当前结果中的最高值。",
            "severity": "success",
        }
    )
    if low_value < 0:
        insights.append(
            {
                "type": "risk",
                "title": f"{_label_for_row(low_row, payload.columns, main_metric)} 出现负值",
                "description": f"{main_metric} 为 {round(low_value, 2)}，建议优先核查该分类或明细。",
                "severity": "warning",
            }
        )
    else:
        insights.append(
            {
                "type": "bottom_driver",
                "title": f"{_label_for_row(low_row, payload.columns, main_metric)} 最低",
                "description": f"{main_metric} 为 {round(low_value, 2)}，可作为下钻对比入口。",
                "severity": "info",
            }
        )

    time_column = _time_column(payload.columns)
    if time_column and len(values) >= 2:
        sorted_rows = sorted(rows, key=lambda row: str(row.get(time_column, "")))
        first = _to_number(sorted_rows[0].get(main_metric))
        last = _to_number(sorted_rows[-1].get(main_metric))
        if first is not None and last is not None and first != 0:
            change = (last - first) / abs(first) * 100
            insights.append(
                {
                    "type": "trend",
                    "title": f"{main_metric} 趋势 {'上升' if change >= 0 else '下降'}",
                    "description": f"从 {sorted_rows[0].get(time_column)} 到 {sorted_rows[-1].get(time_column)} 变化 {round(change, 1)}%。",
                    "severity": "success" if change >= 0 else "warning",
                }
            )

    result = {
        "insights": insights[: max(1, payload.max_items)],
        "summary": f"发现 {len(insights)} 条自动洞察，建议从最高贡献项和异常低值开始定位。",
        "metadata": {"row_count": len(rows), "numeric_columns": numeric_columns, "primary_metric": main_metric},
    }
    return await _enhance_auto_insights_with_llm(payload, result, rows)


@router.post("/anomaly-attribution")
async def anomaly_attribution(
    payload: AnomalyAttributionRequest,
    current_user: User = Depends(get_current_user),
):
    del current_user
    rows = payload.rows[:1000]
    numeric_columns = _numeric_columns(payload.columns, rows)
    metric_column = payload.metric_column if payload.metric_column in numeric_columns else (numeric_columns[0] if numeric_columns else None)
    if not rows or not metric_column:
        return {
            "metric_column": metric_column,
            "drivers": [],
            "summary": "当前结果没有可用于归因的数值指标。",
            "recommendations": ["补充数值指标后再做异常归因"],
            "confidence": "low",
            "llm_enhanced": False,
            "llm_model": None,
        }

    dimensions = [column for column in payload.dimension_columns if column in payload.columns and column != metric_column]
    if not dimensions:
        dimensions = _dimension_columns(payload.columns, rows, numeric_columns)[:3]

    total_abs = sum(abs(_to_number(row.get(metric_column)) or 0) for row in rows) or 1
    drivers: list[dict] = []
    for dimension in dimensions:
        grouped: dict[str, float] = {}
        for row in rows:
            key = str(row.get(dimension, "未分组"))
            grouped[key] = grouped.get(key, 0) + (_to_number(row.get(metric_column)) or 0)
        for value, contribution in grouped.items():
            drivers.append(
                {
                    "dimension": dimension,
                    "value": value,
                    "contribution": round(contribution, 2),
                    "share": round(abs(contribution) / total_abs * 100, 1),
                    "impact": "negative" if contribution < 0 else "positive",
                }
            )

    drivers.sort(key=lambda item: abs(item["contribution"]), reverse=True)
    drivers = drivers[: max(1, payload.max_drivers)]
    top = drivers[0] if drivers else None
    recommendations = [
        "优先下钻最高贡献分类，核对明细、时间段和数据更新时间。",
        "将异常分类创建为行动项，指定负责人跟踪处理结果。",
    ]
    if top and top["impact"] == "negative":
        recommendations.insert(0, f"重点核查 {top['dimension']}={top['value']} 的负向贡献。")
    elif top:
        recommendations.insert(0, f"重点解释 {top['dimension']}={top['value']} 的贡献来源。")

    result = {
        "metric_column": metric_column,
        "drivers": drivers,
        "summary": f"按 {', '.join(dimensions) if dimensions else '可用维度'} 拆解，识别 {len(drivers)} 个主要驱动项。",
        "recommendations": recommendations,
        "confidence": "medium" if dimensions else "low",
    }
    return await _enhance_attribution_with_llm(payload, result, rows)
