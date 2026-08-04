"""Embed token management and public embed data endpoints."""
from __future__ import annotations

import logging
import secrets
from datetime import datetime
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

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


class EmbedChartData(BaseModel):
    resource_id: int
    title: str
    chart_type: str | None = None
    columns: list[str] = []
    rows: list[dict] = []
    error: str | None = None


class EmbedPublicData(BaseModel):
    resource_type: str
    resource_id: int
    title: str
    chart_type: str | None = None
    columns: list[str] = []
    rows: list[dict] = []
    # Populated for dashboards: one entry per chart component.
    charts: list[EmbedChartData] = []


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

def _parse_allowed_domains(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [d.strip().lower() for d in raw.split(",") if d.strip()]


def _request_host(request: Request) -> str | None:
    """Best-effort caller origin host from the Origin, then Referer header."""
    for header in ("origin", "referer"):
        value = request.headers.get(header)
        if value:
            host = urlparse(value).hostname
            if host:
                return host.lower()
    return None


def _enforce_allowed_domains(record: EmbedToken, request: Request) -> None:
    allowed = _parse_allowed_domains(record.allowed_domains)
    if not allowed:
        return  # empty allowlist = embeddable anywhere
    host = _request_host(request)
    if host is None:
        # A restriction is configured but the caller sent no Origin/Referer to check.
        raise HTTPException(status_code=403, detail="该嵌入令牌限制了来源域名，缺少 Origin/Referer")
    # Match exact host or any subdomain of an allowed domain.
    if any(host == domain or host.endswith("." + domain) for domain in allowed):
        return
    raise HTTPException(status_code=403, detail="来源域名不在该嵌入令牌的允许列表内")


def _dashboard_chart_components(dashboard: Dashboard) -> list[dict]:
    layout = dashboard.layout_json if isinstance(dashboard.layout_json, dict) else {}
    return [c for c in (layout.get("components") or []) if isinstance(c, dict) and c.get("pinned_chart_id")]


def resolve_dashboard_public_data(db: Session, dashboard: Dashboard) -> EmbedPublicData:
    """渲染公开看板：按 layout_json 的组件逐个执行图表 SQL，组装成与 embed 一致的数据结构。

    单个图表失败不影响整块看板，仅在该图表上标记 error。供 share_token 公开分享页与
    embed token 看板页复用，保证两条公开访问路径渲染逻辑一致。
    """
    charts: list[EmbedChartData] = []
    for component in _dashboard_chart_components(dashboard):
        chart = db.query(PinnedChart).filter(PinnedChart.id == component["pinned_chart_id"]).first()
        if not chart:
            continue
        title = component.get("title") or chart.title
        ds = _get_chart_datasource(db, chart.datasource_id)
        if not ds:
            charts.append(EmbedChartData(resource_id=chart.id, title=title, error="数据源不存在"))
            continue
        try:
            result = _execute_chart_sql(ds, chart.sql_query)
            charts.append(EmbedChartData(
                resource_id=chart.id,
                title=title,
                chart_type=chart.chart_type,
                columns=result["columns"],
                rows=result["rows"],
            ))
        except Exception as exc:
            logger.warning("Public dashboard %s chart %s failed: %s", dashboard.id, chart.id, exc)
            charts.append(EmbedChartData(
                resource_id=chart.id,
                title=title,
                chart_type=chart.chart_type,
                error="数据查询失败",
            ))
    return EmbedPublicData(
        resource_type="dashboard",
        resource_id=dashboard.id,
        title=dashboard.title,
        charts=charts,
    )


@router.get("/public/{token}", response_model=EmbedPublicData)
def get_embed_public_data(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
):
    record = db.query(EmbedToken).filter(EmbedToken.token == token).first()
    if not record:
        raise HTTPException(status_code=404, detail="embed token 无效")

    if record.expires_at and record.expires_at < datetime.utcnow():
        raise HTTPException(status_code=403, detail="embed token 已过期")

    _enforce_allowed_domains(record, request)

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
        return resolve_dashboard_public_data(db, dashboard)

    raise HTTPException(status_code=400, detail="不支持的资源类型")
