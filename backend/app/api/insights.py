from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.datasource import DataSource
from app.models.metric import Metric
from app.models.user import User

router = APIRouter(prefix="/insights", tags=["insights"])


class MetricExplainRequest(BaseModel):
    metric_id: int
    question: str | None = None


class ChartRecommendRequest(BaseModel):
    columns: list[str]
    rows: list[dict] = []


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
