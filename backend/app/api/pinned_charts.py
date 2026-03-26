from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional, List
from app.api.auth import get_current_user
from app.db.session import get_db, get_datasource_engine
from app.models.datasource import DataSource
from app.models.pinned_chart import PinnedChart
from app.models.user import User

router = APIRouter(prefix="/pinned-charts", tags=["pinned-charts"])


class PinnedChartCreate(BaseModel):
    title: str
    description: Optional[str] = None
    sql_query: str
    chart_type: str = "bar"
    sort_order: str = "desc"
    datasource_id: Optional[int] = None


class PinnedChartUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    chart_type: Optional[str] = None
    sort_order: Optional[str] = None
    display_order: Optional[int] = None


class PinnedChartOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    sql_query: str
    chart_type: str
    sort_order: str
    display_order: int
    datasource_id: Optional[int] = None

    class Config:
        from_attributes = True


class PinnedChartWithData(BaseModel):
    id: int
    title: str
    description: Optional[str]
    chart_type: str
    sort_order: str
    columns: List[str]
    rows: List[dict]


@router.post("", response_model=PinnedChartOut)
def create_pinned_chart(
    payload: PinnedChartCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    max_order = db.query(PinnedChart).filter(
        PinnedChart.user_id == current_user.id
    ).count()

    chart = PinnedChart(
        user_id=current_user.id,
        datasource_id=payload.datasource_id,
        title=payload.title,
        description=payload.description,
        sql_query=payload.sql_query,
        chart_type=payload.chart_type,
        sort_order=payload.sort_order,
        display_order=max_order,
    )
    db.add(chart)
    db.commit()
    db.refresh(chart)
    return chart


@router.get("", response_model=List[PinnedChartOut])
def list_pinned_charts(
    datasource_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(PinnedChart).filter(PinnedChart.user_id == current_user.id)
    if datasource_id:
        query = query.filter(PinnedChart.datasource_id == datasource_id)
    charts = query.order_by(PinnedChart.display_order).all()
    return charts


@router.get("/with-data", response_model=List[PinnedChartWithData])
def list_pinned_charts_with_data(
    datasource_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(PinnedChart).filter(PinnedChart.user_id == current_user.id)
    if datasource_id:
        query = query.filter(PinnedChart.datasource_id == datasource_id)
    charts = query.order_by(PinnedChart.display_order).all()

    result = []
    for chart in charts:
        try:
            # Get the datasource engine for this chart
            ds = None
            if chart.datasource_id:
                ds = db.query(DataSource).filter(DataSource.id == chart.datasource_id).first()
            if not ds:
                ds = db.query(DataSource).filter(DataSource.is_active == 1).first()

            if not ds:
                raise Exception("No datasource configured")

            ds_engine = get_datasource_engine(ds.database_url)
            with ds_engine.connect() as conn:
                result_proxy = conn.execute(text(chart.sql_query))
                columns = list(result_proxy.keys())
                rows = [dict(row._mapping) for row in result_proxy.fetchall()]
                result.append({
                    "id": chart.id,
                    "title": chart.title,
                    "description": chart.description,
                    "chart_type": chart.chart_type,
                    "sort_order": chart.sort_order,
                    "columns": columns,
                    "rows": rows,
                })
        except Exception:
            result.append({
                "id": chart.id,
                "title": chart.title,
                "description": chart.description,
                "chart_type": chart.chart_type,
                "sort_order": chart.sort_order,
                "columns": [],
                "rows": [],
            })
    return result


@router.put("/{chart_id}", response_model=PinnedChartOut)
def update_pinned_chart(
    chart_id: int,
    payload: PinnedChartUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    chart = db.query(PinnedChart).filter(
        PinnedChart.id == chart_id,
        PinnedChart.user_id == current_user.id
    ).first()

    if not chart:
        raise HTTPException(status_code=404, detail="图表不存在")

    if payload.title is not None:
        chart.title = payload.title
    if payload.description is not None:
        chart.description = payload.description
    if payload.chart_type is not None:
        chart.chart_type = payload.chart_type
    if payload.sort_order is not None:
        chart.sort_order = payload.sort_order
    if payload.display_order is not None:
        chart.display_order = payload.display_order

    db.commit()
    db.refresh(chart)
    return chart


@router.delete("/{chart_id}")
def delete_pinned_chart(
    chart_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    chart = db.query(PinnedChart).filter(
        PinnedChart.id == chart_id,
        PinnedChart.user_id == current_user.id
    ).first()

    if not chart:
        raise HTTPException(status_code=404, detail="图表不存在")

    db.delete(chart)
    db.commit()
    return {"status": "ok"}
