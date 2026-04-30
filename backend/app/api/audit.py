import json
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.permissions import require_org_admin_or_above
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.audit import AuditLogListResponse, AuditLogOut

router = APIRouter(prefix="/audit-logs", tags=["audit"])


def _detail_from_json(raw_value: str | None):
    if not raw_value:
        return None
    try:
        return json.loads(raw_value)
    except (json.JSONDecodeError, TypeError):
        return raw_value


def _to_out(log: AuditLog) -> AuditLogOut:
    return AuditLogOut(
        id=log.id,
        actor_user_id=log.actor_user_id,
        actor_username=log.actor_username,
        actor_role=log.actor_role,
        org_id=log.org_id,
        action=log.action,
        resource_type=log.resource_type,
        resource_id=log.resource_id,
        resource_name=log.resource_name,
        status=log.status,
        message=log.message,
        detail=_detail_from_json(log.detail_json),
        ip_address=log.ip_address,
        created_at=log.created_at,
    )


@router.get("", response_model=AuditLogListResponse)
def list_audit_logs(
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    status: Optional[str] = None,
    actor_user_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_org_admin_or_above(current_user)

    query = db.query(AuditLog)
    if current_user.role != "super_admin":
        query = query.filter(AuditLog.org_id == current_user.org_id)
    if action:
        query = query.filter(AuditLog.action == action)
    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type)
    if status:
        query = query.filter(AuditLog.status == status)
    if actor_user_id:
        query = query.filter(AuditLog.actor_user_id == actor_user_id)

    page = max(page, 1)
    page_size = min(max(page_size, 1), 200)
    total = query.count()
    items = (
        query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return AuditLogListResponse(total=total, items=[_to_out(item) for item in items])
