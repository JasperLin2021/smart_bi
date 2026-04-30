from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.api.dashboards import create_dashboard
from app.db.session import get_db
from app.models.user import User
from app.schemas.dashboard_center import DashboardCreate, DashboardOut

router = APIRouter(prefix="/dashboard-templates", tags=["dashboard_templates"])

TEMPLATES = [
    {
        "id": "sales",
        "name": "销售经营模板",
        "description": "销售额、订单量、区域排行和月度趋势",
        "layout_json": {
            "components": [
                {"id": "sales-kpi", "title": "销售额", "chart_type": "kpi", "x": 0, "y": 0, "w": 3, "h": 2},
                {"id": "sales-trend", "title": "月度趋势", "chart_type": "line", "x": 3, "y": 0, "w": 6, "h": 3},
                {"id": "sales-rank", "title": "区域排行", "chart_type": "bar", "x": 9, "y": 0, "w": 3, "h": 3},
            ]
        },
    },
    {
        "id": "quality",
        "name": "质量分析模板",
        "description": "良率、不良分布、工站异常和明细追踪",
        "layout_json": {
            "components": [
                {"id": "quality-yield", "title": "良率", "chart_type": "kpi", "x": 0, "y": 0, "w": 3, "h": 2},
                {"id": "quality-ng", "title": "不良类型分布", "chart_type": "pie", "x": 3, "y": 0, "w": 4, "h": 3},
                {"id": "quality-station", "title": "工站异常排行", "chart_type": "horizontal_bar", "x": 7, "y": 0, "w": 5, "h": 3},
            ]
        },
    },
    {
        "id": "finance",
        "name": "财务指标模板",
        "description": "收入、成本、毛利率和预算达成",
        "layout_json": {
            "components": [
                {"id": "finance-revenue", "title": "收入", "chart_type": "kpi", "x": 0, "y": 0, "w": 3, "h": 2},
                {"id": "finance-margin", "title": "毛利率", "chart_type": "line", "x": 3, "y": 0, "w": 5, "h": 3},
                {"id": "finance-budget", "title": "预算达成", "chart_type": "combo", "x": 8, "y": 0, "w": 4, "h": 3},
            ]
        },
    },
]


@router.get("")
def list_dashboard_templates(current_user: User = Depends(get_current_user)):
    del current_user
    return {"items": TEMPLATES}


@router.post("/{template_id}/dashboards", response_model=DashboardOut)
def create_dashboard_from_template(
    template_id: str,
    title: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    template = next((item for item in TEMPLATES if item["id"] == template_id), None)
    if not template:
        raise HTTPException(status_code=404, detail="看板模板不存在")
    return create_dashboard(
        DashboardCreate(
            title=title or template["name"],
            description=template["description"],
            layout_json=template["layout_json"],
            filters_json={},
            visibility="private",
        ),
        db=db,
        current_user=current_user,
    )
