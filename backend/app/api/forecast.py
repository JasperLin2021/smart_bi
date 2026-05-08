"""Time-series forecasting endpoint using linear regression."""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from typing import Any

import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.pinned_charts import _execute_chart_sql, _get_accessible_chart_datasource
from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.user import User

router = APIRouter(prefix="/forecast", tags=["forecast"])


class ForecastRequest(BaseModel):
    datasource_id: int | None = None
    sql_query: str
    periods: int = 6
    date_col: str | None = None
    value_col: str | None = None


class ForecastPoint(BaseModel):
    label: str
    value: float
    is_forecast: bool = False


class ForecastResponse(BaseModel):
    date_col: str
    value_col: str
    points: list[ForecastPoint]


def _detect_date_col(columns: list[str], rows: list[dict]) -> str | None:
    date_keywords = ("date", "time", "day", "month", "year", "period", "week", "stat")
    for col in columns:
        if any(kw in col.lower() for kw in date_keywords):
            return col
    # Fallback: first string column
    for col in columns:
        sample = next((r[col] for r in rows if r.get(col) is not None), None)
        if isinstance(sample, (str, date, datetime)):
            return col
    return columns[0] if columns else None


def _detect_value_col(columns: list[str], date_col: str, rows: list[dict]) -> str | None:
    numeric_keywords = ("count", "amount", "total", "sum", "value", "num", "qty", "revenue", "sales")
    candidates = [c for c in columns if c != date_col]
    for col in candidates:
        if any(kw in col.lower() for kw in numeric_keywords):
            sample = next((r[col] for r in rows if r.get(col) is not None), None)
            if sample is not None and _is_numeric(sample):
                return col
    # First numeric column
    for col in candidates:
        sample = next((r[col] for r in rows if r.get(col) is not None), None)
        if sample is not None and _is_numeric(sample):
            return col
    return candidates[0] if candidates else None


def _is_numeric(v: Any) -> bool:
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False


def _parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        s = value.strip()
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m", "%Y%m%d", "%Y"):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
        # Try partial match for strings like "2024-11-01 00:00:00"
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(s[:19], fmt).date()
            except ValueError:
                continue
    return None


def _extrapolate_label(last_date: date, step: int, avg_delta_days: float) -> str:
    d = last_date + timedelta(days=int(avg_delta_days * step))
    return str(d)


@router.post("", response_model=ForecastResponse)
def run_forecast(
    payload: ForecastRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sql = payload.sql_query.strip()
    if not sql:
        raise HTTPException(status_code=400, detail="SQL不能为空")

    datasource = _get_accessible_chart_datasource(db, payload.datasource_id, current_user)
    if not datasource:
        raise HTTPException(status_code=400, detail="请先配置数据源")

    try:
        result = _execute_chart_sql(datasource, sql)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"SQL执行失败: {exc}")

    columns: list[str] = result["columns"]
    rows: list[dict] = result["rows"]
    if not rows:
        raise HTTPException(status_code=400, detail="查询结果为空，无法预测")

    date_col = payload.date_col or _detect_date_col(columns, rows)
    value_col = payload.value_col or _detect_value_col(columns, date_col or "", rows)

    if not date_col or not value_col:
        raise HTTPException(status_code=400, detail="无法自动检测时间列或数值列")

    # Parse and sort
    parsed: list[tuple[date, float]] = []
    for row in rows:
        d = _parse_date(row.get(date_col))
        v = row.get(value_col)
        if d is not None and _is_numeric(v):
            parsed.append((d, float(v)))
    parsed.sort(key=lambda x: x[0])

    if len(parsed) < 2:
        raise HTTPException(status_code=400, detail="历史数据点不足（至少需要2个）")

    dates, values = zip(*parsed)
    epoch = dates[0]
    x = np.array([(d - epoch).days for d in dates], dtype=float)
    y = np.array(values, dtype=float)

    # Linear regression
    coeffs = np.polyfit(x, y, 1)
    slope, intercept = float(coeffs[0]), float(coeffs[1])

    # Average step for future labels
    avg_delta = float((dates[-1] - dates[0]).days) / max(len(dates) - 1, 1)

    # Historical points
    points: list[ForecastPoint] = [
        ForecastPoint(label=str(d), value=round(v, 4), is_forecast=False)
        for d, v in zip(dates, values)
    ]

    # Forecast points
    last_x = x[-1]
    last_date = dates[-1]
    for i in range(1, payload.periods + 1):
        future_x = last_x + avg_delta * i
        future_val = slope * future_x + intercept
        future_val = max(future_val, 0)  # no negative
        future_label = _extrapolate_label(last_date, i, avg_delta)
        points.append(ForecastPoint(label=future_label, value=round(future_val, 4), is_forecast=True))

    return ForecastResponse(date_col=date_col, value_col=value_col, points=points)
