from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional, List
from app.api.auth import get_current_user
from app.core.excel_executor import execute_excel_query
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


class PinnedChartPreviewRequest(BaseModel):
    sql_query: str
    datasource_id: Optional[int] = None


class PinnedChartPreviewResult(BaseModel):
    columns: List[str]
    rows: List[dict]


def _get_chart_datasource(db: Session, datasource_id: int | None) -> DataSource | None:
    if datasource_id:
        return db.query(DataSource).filter(DataSource.id == datasource_id).first()
    return db.query(DataSource).filter(DataSource.is_active == 1).first()


def _execute_chart_sql(datasource: DataSource, sql_query: str) -> dict:
    if datasource.source_type == "excel":
        return execute_excel_query(datasource.database_url, sql_query)

    ds_engine = get_datasource_engine(datasource.database_url)
    with ds_engine.connect() as conn:
        result_proxy = conn.execute(text(sql_query))
        columns = list(result_proxy.keys())
        rows = [dict(row._mapping) for row in result_proxy.fetchall()]
    return {"columns": columns, "rows": rows}


@router.post("", response_model=PinnedChartOut)
def create_pinned_chart(
    payload: PinnedChartCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    datasource_id = payload.datasource_id
    if datasource_id is None:
        active_datasource = db.query(DataSource).filter(DataSource.is_active == 1).first()
        datasource_id = active_datasource.id if active_datasource else None

    max_order = db.query(PinnedChart).filter(
        PinnedChart.user_id == current_user.id
    ).count()

    chart = PinnedChart(
        user_id=current_user.id,
        datasource_id=datasource_id,
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


@router.post("/preview", response_model=PinnedChartPreviewResult)
def preview_pinned_chart(
    payload: PinnedChartPreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    del current_user
    sql_query = payload.sql_query.strip()
    if not sql_query:
        raise HTTPException(status_code=400, detail="SQL不能为空")

    datasource = _get_chart_datasource(db, payload.datasource_id)
    if not datasource:
        raise HTTPException(status_code=400, detail="请先选择或配置数据源")

    try:
        result = _execute_chart_sql(datasource, sql_query)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"SQL执行失败: {exc}")
    return PinnedChartPreviewResult(columns=result["columns"], rows=result["rows"])


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

            query_result = _execute_chart_sql(ds, chart.sql_query)
            columns = query_result["columns"]
            rows = query_result["rows"]

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
