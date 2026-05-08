"""Embed token management and public embed data endpoints."""
from __future__ import annotations

import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.pinned_charts import _execute_chart_sql, _get_chart_datasource, can_access_pinned_chart
from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.dashboard_config import Dashboard
from app.models.embed_token import EmbedToken
from app.models.pinned_chart import PinnedChart
from app.models.user import User

router = APIRouter(prefix="/embed", tags=["embed"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class EmbedTokenCreate(BaseModel):
    label: str = ""
    resource_type: str  # "chart" | "dashboard"
    resource_id: int
    allowed_domains: str = ""  # comma-separated, empty = all
    expires_days: int | None = None  # None = never


class EmbedTokenOut(BaseModel):
    id: int
    token: str
    label: str | None
    resource_type: str
    resource_id: int
    allowed_domains: str | None
    expires_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class EmbedPublicData(BaseModel):
    resource_type: str
    resource_id: int
    title: str
    chart_type: str | None = None
    columns: list[str] = []
    rows: list[dict] = []


# ── CRUD (requires auth) ──────────────────────────────────────────────────────

def _can_create_dashboard_embed(user: User, dashboard: Dashboard) -> bool:
    if user.role == "super_admin":
        return True
    if user.role == "org_admin" and dashboard.org_id == user.org_id:
        return True
    return dashboard.owner_id == user.id


def _assert_embed_resource_access(
    payload: EmbedTokenCreate,
    db: Session,
    current_user: User,
) -> None:
    if payload.resource_type == "dashboard":
        dashboard = db.query(Dashboard).filter(Dashboard.id == payload.resource_id).first()
        if not dashboard:
            raise HTTPException(status_code=404, detail="看板不存在")
        if not _can_create_dashboard_embed(current_user, dashboard):
            raise HTTPException(status_code=403, detail="无权创建此看板的嵌入令牌")
        return

    chart = db.query(PinnedChart).filter(PinnedChart.id == payload.resource_id).first()
    if not chart:
        raise HTTPException(status_code=404, detail="图表不存在")
    if not can_access_pinned_chart(db, current_user, chart):
        raise HTTPException(status_code=403, detail="无权创建此图表的嵌入令牌")


@router.get("/tokens", response_model=list[EmbedTokenOut])
def list_embed_tokens(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(EmbedToken).filter(EmbedToken.created_by == current_user.id).all()


@router.post("/tokens", response_model=EmbedTokenOut)
def create_embed_token(
    payload: EmbedTokenCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.resource_type not in ("chart", "dashboard"):
        raise HTTPException(status_code=400, detail="resource_type 必须为 chart 或 dashboard")

    _assert_embed_resource_access(payload, db, current_user)

    expires_at = None
    if payload.expires_days:
        from datetime import timedelta
        expires_at = datetime.utcnow() + timedelta(days=payload.expires_days)

    token = EmbedToken(
        token=secrets.token_urlsafe(32),
        label=payload.label or None,
        resource_type=payload.resource_type,
        resource_id=payload.resource_id,
        allowed_domains=payload.allowed_domains or None,
        created_by=current_user.id,
        expires_at=expires_at,
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return token


@router.delete("/tokens/{token_id}")
def delete_embed_token(
    token_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    token = db.query(EmbedToken).filter(
        EmbedToken.id == token_id,
        EmbedToken.created_by == current_user.id,
    ).first()
    if not token:
        raise HTTPException(status_code=404, detail="Token不存在")
    db.delete(token)
    db.commit()
    return {"ok": True}


# ── Public data endpoint (no auth) ───────────────────────────────────────────

@router.get("/public/{token}", response_model=EmbedPublicData)
def get_embed_public_data(
    token: str,
    db: Session = Depends(get_db),
):
    record = db.query(EmbedToken).filter(EmbedToken.token == token).first()
    if not record:
        raise HTTPException(status_code=404, detail="embed token 无效")

    if record.expires_at and record.expires_at < datetime.utcnow():
        raise HTTPException(status_code=403, detail="embed token 已过期")

    if record.resource_type == "chart":
        chart = db.query(PinnedChart).filter(PinnedChart.id == record.resource_id).first()
        if not chart:
            raise HTTPException(status_code=404, detail="图表不存在")
        ds = _get_chart_datasource(db, chart.datasource_id)
        if not ds:
            raise HTTPException(status_code=400, detail="数据源不存在")
        try:
            result = _execute_chart_sql(ds, chart.sql_query)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"数据查询失败: {exc}")
        return EmbedPublicData(
            resource_type="chart",
            resource_id=chart.id,
            title=chart.title,
            chart_type=chart.chart_type,
            columns=result["columns"],
            rows=result["rows"],
        )

    if record.resource_type == "dashboard":
        dashboard = db.query(Dashboard).filter(Dashboard.id == record.resource_id).first()
        if not dashboard:
            raise HTTPException(status_code=404, detail="看板不存在")
        return EmbedPublicData(
            resource_type="dashboard",
            resource_id=dashboard.id,
            title=dashboard.title,
            columns=[],
            rows=[],
        )

    raise HTTPException(status_code=400, detail="不支持的资源类型")
