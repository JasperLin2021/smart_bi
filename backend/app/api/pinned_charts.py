from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional, List
import time

from app.api.auth import get_current_user
from app.core.safe_delete import assert_pinned_chart_can_delete
from app.core.excel_executor import execute_excel_query
from app.db.session import get_db, get_datasource_engine
from app.models.dashboard_config import Dashboard
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


class PinnedChartAddToDashboard(PinnedChartCreate):
    dashboard_id: int


class PinnedChartUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    sql_query: Optional[str] = None
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
    sql_query: str
    datasource_id: Optional[int] = None
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


class PinnedChartAddToDashboardResponse(BaseModel):
    chart: PinnedChartOut
    dashboard_id: int
    component_id: str


def _get_chart_datasource(db: Session, datasource_id: int | None) -> DataSource | None:
    if datasource_id:
        return db.query(DataSource).filter(DataSource.id == datasource_id).first()
    return db.query(DataSource).filter(DataSource.is_active == 1).first()


def can_access_datasource(user: User, datasource: DataSource | None) -> bool:
    if not datasource:
        return False
    if getattr(user, "role", None) == "super_admin":
        return True
    user_org_id = getattr(user, "org_id", None)
    datasource_org_id = getattr(datasource, "org_id", None)
    if user_org_id is None or datasource_org_id is None:
        return True
    return user_org_id == datasource_org_id


def _get_accessible_chart_datasource(
    db: Session,
    datasource_id: int | None,
    current_user: User,
) -> DataSource | None:
    if datasource_id is not None:
        datasource = db.query(DataSource).filter(DataSource.id == datasource_id).first()
        if not datasource:
            raise HTTPException(status_code=404, detail="数据源不存在")
        if not can_access_datasource(current_user, datasource):
            raise HTTPException(status_code=403, detail="无权访问此数据源")
        return datasource

    query = db.query(DataSource).filter(DataSource.is_active == 1)
    if getattr(current_user, "role", None) != "super_admin" and getattr(current_user, "org_id", None) is not None:
        query = query.filter(DataSource.org_id == current_user.org_id)
    return query.first()


def can_access_pinned_chart(db: Session, user: User, chart: PinnedChart | None) -> bool:
    if not chart:
        return False
    if getattr(user, "role", None) == "super_admin":
        return True
    if chart.user_id == getattr(user, "id", None):
        return True
    if getattr(user, "role", None) != "org_admin":
        return False
    datasource = (
        db.query(DataSource).filter(DataSource.id == chart.datasource_id).first()
        if chart.datasource_id
        else None
    )
    return can_access_datasource(user, datasource)


def _execute_chart_sql(datasource: DataSource, sql_query: str) -> dict:
    if datasource.source_type == "excel":
        return execute_excel_query(datasource.database_url, sql_query)

    ds_engine = get_datasource_engine(datasource.database_url)
    with ds_engine.connect() as conn:
        result_proxy = conn.execute(text(sql_query))
        columns = list(result_proxy.keys())
        rows = [dict(row._mapping) for row in result_proxy.fetchall()]
    return {"columns": columns, "rows": rows}


def _resolve_datasource_id(db: Session, datasource_id: int | None, current_user: User) -> int | None:
    datasource = _get_accessible_chart_datasource(db, datasource_id, current_user)
    return datasource.id if datasource else None


def _can_manage_dashboard(user: User, dashboard: Dashboard) -> bool:
    if user.role == "super_admin":
        return True
    if user.role == "org_admin" and dashboard.org_id == user.org_id:
        return True
    return dashboard.owner_id == user.id


def _default_component_size(chart_type: str) -> dict[str, int]:
    sizes = {
        "kpi": {"w": 3, "h": 2},
        "table": {"w": 12, "h": 4},
        "pie": {"w": 4, "h": 3},
        "donut": {"w": 4, "h": 3},
        "scatter": {"w": 6, "h": 4},
        "combo": {"w": 8, "h": 4},
    }
    return sizes.get(chart_type, {"w": 6, "h": 3})


def _append_chart_to_dashboard(dashboard: Dashboard, chart: PinnedChart) -> str:
    layout = dashboard.layout_json if isinstance(dashboard.layout_json, dict) else {}
    components = list(layout.get("components") or [])
    size = _default_component_size(chart.chart_type)
    component_id = f"component-{chart.id}-{int(time.time() * 1000)}"
    components.append(
        {
            "id": component_id,
            "pinned_chart_id": chart.id,
            "title": chart.title,
            "description": chart.description,
            "chart_type": chart.chart_type,
            "sort_order": chart.sort_order,
            "x": 0,
            "y": len(components),
            "w": size["w"],
            "h": size["h"],
        }
    )
    dashboard.layout_json = {**layout, "components": components}
    dashboard.version = (dashboard.version or 1) + 1
    return component_id


@router.post("", response_model=PinnedChartOut)
def create_pinned_chart(
    payload: PinnedChartCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    datasource_id = _resolve_datasource_id(db, payload.datasource_id, current_user)

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


@router.post("/add-to-dashboard", response_model=PinnedChartAddToDashboardResponse)
def add_pinned_chart_to_dashboard(
    payload: PinnedChartAddToDashboard,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dashboard = db.query(Dashboard).filter(Dashboard.id == payload.dashboard_id).first()
    if not dashboard:
        raise HTTPException(status_code=404, detail="看板不存在")
    if not _can_manage_dashboard(current_user, dashboard):
        raise HTTPException(status_code=403, detail="无权修改此看板")

    datasource_id = _resolve_datasource_id(db, payload.datasource_id, current_user)
    max_order = db.query(PinnedChart).filter(PinnedChart.user_id == current_user.id).count()
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
    db.flush()
    component_id = _append_chart_to_dashboard(dashboard, chart)
    db.commit()
    db.refresh(chart)
    return PinnedChartAddToDashboardResponse(
        chart=PinnedChartOut.model_validate(chart),
        dashboard_id=dashboard.id,
        component_id=component_id,
    )


@router.post("/preview", response_model=PinnedChartPreviewResult)
def preview_pinned_chart(
    payload: PinnedChartPreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sql_query = payload.sql_query.strip()
    if not sql_query:
        raise HTTPException(status_code=400, detail="SQL不能为空")

    datasource = _get_accessible_chart_datasource(db, payload.datasource_id, current_user)
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
        _get_accessible_chart_datasource(db, datasource_id, current_user)
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
        _get_accessible_chart_datasource(db, datasource_id, current_user)
        query = query.filter(PinnedChart.datasource_id == datasource_id)
    charts = query.order_by(PinnedChart.display_order).all()

    result = []
    for chart in charts:
        try:
            # Get the datasource engine for this chart
            ds = _get_accessible_chart_datasource(db, chart.datasource_id, current_user)

            if not ds:
                raise Exception("No datasource configured")

            query_result = _execute_chart_sql(ds, chart.sql_query)
            columns = query_result["columns"]
            rows = query_result["rows"]

            result.append({
                "id": chart.id,
                "title": chart.title,
                "description": chart.description,
                "sql_query": chart.sql_query,
                "datasource_id": chart.datasource_id,
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
                "sql_query": chart.sql_query,
                "datasource_id": chart.datasource_id,
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
    if payload.sql_query is not None:
        chart.sql_query = payload.sql_query
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

    assert_pinned_chart_can_delete(db, chart)
    db.delete(chart)
    db.commit()
    return {"status": "ok"}
