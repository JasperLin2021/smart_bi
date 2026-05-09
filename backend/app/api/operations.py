import os
import shutil
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import inspect, or_
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.big_screen import BigScreen
from app.models.catalog import DataAsset
from app.models.dashboard_config import Dashboard
from app.models.dataset import Dataset, DatasetRefreshLog
from app.models.query import QueryHistory
from app.models.datasource import DataSource
from app.models.metric import Metric
from app.models.organization import Organization
from app.models.user import User

router = APIRouter(prefix="/operations", tags=["operations"])


def _ensure_operator(user: User) -> None:
    if user.role not in ("org_admin", "super_admin"):
        raise HTTPException(status_code=403, detail="无权限")


def _scope_org(query, model, user: User):
    if user.role == "super_admin":
        return query
    return query.filter(model.org_id == user.org_id)


def _scope_query_history(query, user: User):
    if user.role == "super_admin":
        return query
    return query.outerjoin(User, QueryHistory.user_id == User.id).filter(
        or_(QueryHistory.org_id == user.org_id, User.org_id == user.org_id)
    )


def _metric_query(db: Session, user: User, dataset_ids: list[int], datasource_ids: list[int]):
    query = db.query(Metric)
    if user.role == "super_admin":
        return query
    filters = []
    if dataset_ids:
        filters.append(Metric.dataset_id.in_(dataset_ids))
    if datasource_ids:
        filters.append(Metric.datasource_id.in_(datasource_ids))
    if not filters:
        return query.filter(False)
    return query.filter(or_(*filters))


def _count(query) -> int:
    if query is None:
        return 0
    return int(query.count() or 0)


def _sum(values) -> int:
    return int(sum(value or 0 for value in values))


def _ratio(part: int, total: int) -> int:
    if total <= 0:
        return 0
    return round(part / total * 100)


def _percent(used: int | float, total: int | float) -> int:
    if total <= 0:
        return 0
    return max(0, min(100, round(used / total * 100)))


def _usage_item(key: str, label: str, used: int, unit: str, description: str, max_used: int) -> dict:
    return {
        "key": key,
        "label": label,
        "used": used,
        "unit": unit,
        "capacity_label": "不限额",
        "share_percent": _ratio(used, max_used),
        "status": "normal",
        "description": description,
    }


def _date_key(value) -> str | None:
    if not value:
        return None
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).date().isoformat()
        except ValueError:
            return None
    return value.date().isoformat()


def _has_table(db: Session, model) -> bool:
    return inspect(db.get_bind()).has_table(model.__tablename__)


def _read_memory_usage() -> dict:
    values: dict[str, int] = {}
    try:
        with open("/proc/meminfo", encoding="utf-8") as meminfo:
            for line in meminfo:
                key, _, raw_value = line.partition(":")
                if key in {"MemTotal", "MemAvailable"}:
                    values[key] = int(raw_value.strip().split()[0]) * 1024
    except (OSError, ValueError):
        values = {}

    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable", 0)
    used = max(total - available, 0) if total else 0
    return {
        "label": "内存",
        "used": used,
        "total": total,
        "used_percent": _percent(used, total),
        "unit": "bytes",
        "detail": "主机内存使用率" if total else "当前环境未暴露内存信息",
    }


def _system_resources() -> dict:
    cpu_count = os.cpu_count() or 1
    try:
        load_1m, _, _ = os.getloadavg()
    except OSError:
        load_1m = 0.0

    disk = shutil.disk_usage("/")
    return {
        "cpu_load": {
            "label": "CPU 负载",
            "used": round(load_1m, 2),
            "total": cpu_count,
            "used_percent": _percent(load_1m, cpu_count),
            "unit": "load",
            "detail": f"1 分钟负载 {load_1m:.2f} / {cpu_count} 核",
        },
        "memory": _read_memory_usage(),
        "disk": {
            "label": "磁盘",
            "used": disk.used,
            "total": disk.total,
            "used_percent": _percent(disk.used, disk.total),
            "unit": "bytes",
            "detail": "根目录文件系统占用",
        },
    }


@router.get("/summary")
def get_operations_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_operator(current_user)
    now = datetime.utcnow()
    seven_days_ago = now - timedelta(days=7)

    user_query = db.query(User)
    query_history_query = _scope_query_history(db.query(QueryHistory), current_user)
    if current_user.role != "super_admin":
        user_query = user_query.filter(User.org_id == current_user.org_id)

    audit_query = db.query(AuditLog)
    if current_user.role != "super_admin":
        audit_query = audit_query.filter(AuditLog.org_id == current_user.org_id)

    has_datasources = _has_table(db, DataSource)
    has_metrics = _has_table(db, Metric)
    has_organizations = _has_table(db, Organization)
    has_refresh_logs = _has_table(db, DatasetRefreshLog)

    datasource_query = _scope_org(db.query(DataSource), DataSource, current_user) if has_datasources else None
    dataset_query = _scope_org(db.query(Dataset), Dataset, current_user)
    dashboard_query = _scope_org(db.query(Dashboard), Dashboard, current_user)
    big_screen_query = _scope_org(db.query(BigScreen), BigScreen, current_user)
    asset_query = _scope_org(db.query(DataAsset), DataAsset, current_user)
    refresh_log_query = (
        _scope_org(db.query(DatasetRefreshLog), DatasetRefreshLog, current_user)
        if has_refresh_logs
        else None
    )

    datasource_ids = [item[0] for item in datasource_query.with_entities(DataSource.id).all()] if datasource_query is not None else []
    dataset_rows = dataset_query.with_entities(Dataset.id, Dataset.last_refresh_row_count).all()
    dataset_ids = [item[0] for item in dataset_rows]
    metric_query = _metric_query(db, current_user, dataset_ids, datasource_ids) if has_metrics else None

    active_users = _count(user_query)
    query_count = _count(query_history_query)
    datasource_count = _count(datasource_query)
    dataset_count = _count(dataset_query)
    dashboard_count = _count(dashboard_query)
    big_screen_count = _count(big_screen_query)
    asset_count = _count(asset_query)
    metric_count = _count(metric_query)
    organization_count = _count(db.query(Organization)) if current_user.role == "super_admin" and has_organizations else 1

    published_assets = _count(asset_query.filter(DataAsset.status == "published"))
    draft_assets = _count(asset_query.filter(DataAsset.status == "draft"))
    published_datasets = _count(dataset_query.filter(Dataset.status == "published"))
    draft_datasets = _count(dataset_query.filter(Dataset.status == "draft"))
    published_dashboards = _count(dashboard_query.filter(Dashboard.status == "published"))
    inactive_datasources = _count(datasource_query.filter(DataSource.is_active == 0)) if datasource_query is not None else 0
    materialized_datasets = _count(dataset_query.filter(Dataset.materialization_status == "success"))

    recent_query_rows = query_history_query.filter(QueryHistory.created_at >= seven_days_ago).all()
    queries_7d = len(recent_query_rows)
    audit_error_count = _count(audit_query.filter(AuditLog.status == "error"))
    audit_errors_7d = _count(
        audit_query.filter(AuditLog.status == "error", AuditLog.created_at >= seven_days_ago)
    )
    refresh_failures_7d = (
        _count(
            refresh_log_query.filter(
                DatasetRefreshLog.status.in_(("failed", "error")),
                DatasetRefreshLog.created_at >= seven_days_ago,
            )
        )
        if refresh_log_query is not None
        else 0
    )

    trend_counts = {date_key: 0 for date_key in [(now - timedelta(days=offset)).date().isoformat() for offset in range(6, -1, -1)]}
    for row in recent_query_rows:
        date_key = _date_key(row.created_at)
        if date_key in trend_counts:
            trend_counts[date_key] += 1

    datasource_names = (
        {
            item.id: item.name
            for item in datasource_query.with_entities(DataSource.id, DataSource.name).all()
        }
        if datasource_query is not None
        else {}
    )
    datasource_query_counts = {source_id: 0 for source_id in datasource_names}
    for row in query_history_query.filter(QueryHistory.datasource_id.isnot(None)).all():
        if row.datasource_id in datasource_query_counts:
            datasource_query_counts[row.datasource_id] += 1

    datasource_usage = sorted(
        [
            {
                "id": source_id,
                "name": datasource_names[source_id],
                "query_count": count,
                "share_percent": _ratio(count, max(datasource_query_counts.values() or [0])),
            }
            for source_id, count in datasource_query_counts.items()
        ],
        key=lambda item: item["query_count"],
        reverse=True,
    )[:5]

    resource_counts = {
        "users": active_users,
        "datasources": datasource_count,
        "datasets": dataset_count,
        "dashboards": dashboard_count,
        "big_screens": big_screen_count,
        "metrics": metric_count,
        "catalog_assets": asset_count,
    }
    max_resource_count = max(resource_counts.values() or [0], default=0)

    return {
        "scope": {
            "type": "platform" if current_user.role == "super_admin" else "organization",
            "org_id": None if current_user.role == "super_admin" else current_user.org_id,
            "label": "全平台" if current_user.role == "super_admin" else "当前企业",
        },
        "generated_at": now.isoformat(),
        "active_users": active_users,
        "query_count": query_count,
        "asset_count": asset_count,
        "datasource_count": datasource_count,
        "dashboard_count": dashboard_count,
        "dataset_count": dataset_count,
        "big_screen_count": big_screen_count,
        "metric_count": metric_count,
        "organization_count": organization_count,
        "audit_error_count": audit_error_count,
        "resource_usage": [
            _usage_item("users", "用户账号", active_users, "人", "可登录平台的账号数量", max_resource_count),
            _usage_item("datasources", "数据源", datasource_count, "个", "已接入的数据库、Excel 或业务系统", max_resource_count),
            _usage_item("datasets", "数据集", dataset_count, "个", "业务建模后可复用的数据集", max_resource_count),
            _usage_item("dashboards", "看板", dashboard_count, "个", "经营看板与分析看板", max_resource_count),
            _usage_item("big_screens", "大屏", big_screen_count, "个", "可投屏展示的大屏资产", max_resource_count),
            _usage_item("metrics", "可信指标", metric_count, "个", "已维护的指标口径", max_resource_count),
            _usage_item("catalog_assets", "目录资产", asset_count, "个", "已进入数据目录的可检索资产", max_resource_count),
        ],
        "workload": {
            "queries_total": query_count,
            "queries_7d": queries_7d,
            "audit_errors_total": audit_error_count,
            "audit_errors_7d": audit_errors_7d,
            "avg_queries_per_user_7d": round(queries_7d / active_users, 2) if active_users else 0,
        },
        "asset_health": {
            "published_assets": published_assets,
            "draft_assets": draft_assets,
            "published_asset_ratio": _ratio(published_assets, asset_count),
            "published_datasets": published_datasets,
            "draft_datasets": draft_datasets,
            "published_dashboards": published_dashboards,
            "inactive_datasources": inactive_datasources,
            "dataset_refresh_failures_7d": refresh_failures_7d,
            "materialized_datasets": materialized_datasets,
        },
        "row_usage": {
            "dataset_rows": _sum(row_count for _, row_count in dataset_rows),
            "materialized_datasets": materialized_datasets,
        },
        "system_resources": _system_resources(),
        "query_trend": [
            {"date": date_key, "count": count}
            for date_key, count in trend_counts.items()
        ],
        "datasource_usage": datasource_usage,
    }
