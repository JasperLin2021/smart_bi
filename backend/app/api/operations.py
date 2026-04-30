from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.big_screen import BigScreen
from app.models.catalog import DataAsset
from app.models.dashboard_config import Dashboard
from app.models.dataset import Dataset
from app.models.query import QueryHistory
from app.models.user import User

router = APIRouter(prefix="/operations", tags=["operations"])


def _ensure_operator(user: User) -> None:
    if user.role not in ("org_admin", "super_admin"):
        raise HTTPException(status_code=403, detail="无权限")


def _scope_org(query, model, user: User):
    if user.role == "super_admin":
        return query
    return query.filter(model.org_id == user.org_id)


@router.get("/summary")
def get_operations_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_operator(current_user)

    user_query = db.query(User)
    query_history_query = db.query(QueryHistory).join(User, QueryHistory.user_id == User.id)
    if current_user.role != "super_admin":
        user_query = user_query.filter(User.org_id == current_user.org_id)
        query_history_query = query_history_query.filter(User.org_id == current_user.org_id)

    audit_query = db.query(AuditLog)
    if current_user.role != "super_admin":
        audit_query = audit_query.filter(AuditLog.org_id == current_user.org_id)

    return {
        "active_users": user_query.count(),
        "query_count": query_history_query.count(),
        "asset_count": _scope_org(db.query(DataAsset), DataAsset, current_user).count(),
        "dashboard_count": _scope_org(db.query(Dashboard), Dashboard, current_user).count(),
        "dataset_count": _scope_org(db.query(Dataset), Dataset, current_user).count(),
        "big_screen_count": _scope_org(db.query(BigScreen), BigScreen, current_user).count(),
        "audit_error_count": audit_query.filter(AuditLog.status == "error").count(),
    }
