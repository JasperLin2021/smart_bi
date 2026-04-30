from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import extract, func, inspect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.big_screen import BigScreen
from app.models.dashboard_config import Dashboard
from app.models.datasource import DataSource
from app.models.organization import Organization
from app.models.query import QueryHistory
from app.models.user import User


RESOURCE_LABELS = {
    "users": "用户",
    "datasources": "数据源",
    "dashboards": "看板",
    "big_screens": "大屏",
    "monthly_queries": "月度问数",
}

LIMIT_FIELDS = {
    "users": "user_limit",
    "datasources": "datasource_limit",
    "dashboards": "dashboard_limit",
    "big_screens": "big_screen_limit",
    "monthly_queries": "monthly_query_limit",
}

PLAN_LIMITS: dict[str, dict[str, int | None]] = {
    "free": {
        "users": 5,
        "datasources": 2,
        "dashboards": 3,
        "big_screens": 1,
        "monthly_queries": 500,
    },
    "team": {
        "users": 30,
        "datasources": 10,
        "dashboards": 20,
        "big_screens": 5,
        "monthly_queries": 10000,
    },
    "enterprise": {
        "users": None,
        "datasources": None,
        "dashboards": None,
        "big_screens": None,
        "monthly_queries": None,
    },
}


def normalize_plan_type(plan_type: str | None) -> str:
    value = (plan_type or "team").strip().lower()
    if value not in PLAN_LIMITS:
        raise HTTPException(status_code=400, detail="无效企业套餐")
    return value


def resolve_organization_limits(org: Organization) -> dict[str, int | None]:
    plan_type = normalize_plan_type(getattr(org, "plan_type", None))
    defaults = PLAN_LIMITS[plan_type]
    limits: dict[str, int | None] = {}
    for key, field_name in LIMIT_FIELDS.items():
        explicit = getattr(org, field_name, None)
        limits[key] = explicit if explicit is not None else defaults[key]
    return limits


def _count_monthly_queries(db: Session, org_id: int) -> int:
    now = datetime.utcnow()
    return (
        db.query(func.count(QueryHistory.id))
        .join(User, QueryHistory.user_id == User.id)
        .filter(
            User.org_id == org_id,
            extract("year", QueryHistory.created_at) == now.year,
            extract("month", QueryHistory.created_at) == now.month,
        )
        .scalar()
        or 0
    )


def _has_table(db: Session, table_name: str) -> bool:
    try:
        return inspect(db.get_bind()).has_table(table_name)
    except SQLAlchemyError:
        return False


def _safe_count(db: Session, table_name: str, query) -> int:
    if not _has_table(db, table_name):
        return 0
    try:
        return query.scalar() or 0
    except SQLAlchemyError:
        return 0


def get_organization_usage(db: Session, org_id: int) -> dict[str, Any]:
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="企业不存在")

    usage = {
        "users": _safe_count(db, "users", db.query(func.count(User.id)).filter(User.org_id == org_id)),
        "datasources": _safe_count(
            db,
            "datasources",
            db.query(func.count(DataSource.id)).filter(DataSource.org_id == org_id, DataSource.is_active == 1),
        ),
        "dashboards": _safe_count(db, "dashboards", db.query(func.count(Dashboard.id)).filter(Dashboard.org_id == org_id)),
        "big_screens": _safe_count(db, "big_screens", db.query(func.count(BigScreen.id)).filter(BigScreen.org_id == org_id)),
        "monthly_queries": _count_monthly_queries(db, org_id) if _has_table(db, "query_history") and _has_table(db, "users") else 0,
    }
    limits = resolve_organization_limits(org)
    remaining = {
        key: None if limits[key] is None else max(limits[key] - usage[key], 0)
        for key in limits
    }
    usage_rate = {
        key: 0 if not limits[key] else min(round(usage[key] / limits[key] * 100), 100)
        for key in limits
    }
    return {
        "org_id": org.id,
        "org_name": org.name,
        "plan_type": normalize_plan_type(getattr(org, "plan_type", None)),
        "limits": limits,
        "usage": usage,
        "remaining": remaining,
        "usage_rate": usage_rate,
    }


def assert_can_create_resource(db: Session, org_id: int | None, resource: str) -> None:
    if org_id is None:
        return
    if not _has_table(db, "organizations"):
        return
    if not db.query(Organization).filter(Organization.id == org_id).first():
        return
    usage = get_organization_usage(db, org_id)
    limit = usage["limits"].get(resource)
    current = usage["usage"].get(resource, 0)
    if limit is not None and current >= limit:
        label = RESOURCE_LABELS.get(resource, resource)
        raise HTTPException(status_code=400, detail=f"企业套餐已达到{label}上限（{limit}）")
