from sqlalchemy import func
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends

from app.api.auth import get_current_user
from app.core.olap import get_olap_status
from app.db.session import get_db
from app.models.dataset import Dataset, DatasetRefreshLog
from app.models.datasource import DataSource
from app.models.user import User

router = APIRouter(prefix="/data-access", tags=["data-access"])


def _apply_org_scope(query, model, current_user: User):
    if current_user.role == "super_admin":
        return query
    return query.filter(model.org_id == current_user.org_id)


def _count(query) -> int:
    return int(query.scalar() or 0)


def _olap_status() -> dict:
    try:
        return get_olap_status()
    except Exception as exc:
        return {
            "enabled": False,
            "engine": "Apache Doris",
            "healthy": False,
            "message": f"Doris 状态获取失败: {exc}",
        }


@router.get("/overview")
def get_data_access_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    datasource_base = _apply_org_scope(db.query(DataSource), DataSource, current_user)
    dataset_base = _apply_org_scope(db.query(Dataset), Dataset, current_user)
    refresh_base = _apply_org_scope(db.query(DatasetRefreshLog), DatasetRefreshLog, current_user)

    source_type_rows = (
        _apply_org_scope(
            db.query(DataSource.source_type, func.count(DataSource.id)),
            DataSource,
            current_user,
        )
        .filter(DataSource.is_active == 1)
        .group_by(DataSource.source_type)
        .order_by(DataSource.source_type.asc())
        .all()
    )

    recent_refresh_logs = (
        refresh_base.order_by(DatasetRefreshLog.id.desc())
        .limit(8)
        .all()
    )

    return {
        "datasources": {
            "total": datasource_base.count(),
            "active": datasource_base.filter(DataSource.is_active == 1).count(),
            "inactive": datasource_base.filter(DataSource.is_active != 1).count(),
            "schema_ready": datasource_base.filter(DataSource.schema_metadata.isnot(None)).count(),
        },
        "datasets": {
            "total": dataset_base.count(),
            "published": dataset_base.filter(Dataset.status == "published").count(),
            "draft": dataset_base.filter(Dataset.status == "draft").count(),
            "materialized": dataset_base.filter(Dataset.materialization_status == "ready").count(),
        },
        "sync_tasks": {
            "total": refresh_base.count(),
            "success": refresh_base.filter(DatasetRefreshLog.status == "success").count(),
            "failed": refresh_base.filter(DatasetRefreshLog.status == "error").count(),
            "pending": dataset_base.filter(Dataset.last_refresh_status.is_(None)).count(),
        },
        "source_types": [
            {"type": source_type or "database", "count": count}
            for source_type, count in source_type_rows
        ],
        "olap": _olap_status(),
        "recent_refresh_logs": [
            {
                "id": log.id,
                "dataset_id": log.dataset_id,
                "status": log.status,
                "row_count": log.row_count,
                "message": log.message,
                "created_at": log.created_at,
            }
            for log in recent_refresh_logs
        ],
    }
