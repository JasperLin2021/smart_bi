import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def _serialize_detail(detail: Any | None) -> str | None:
    if detail is None:
        return None
    return json.dumps(detail, ensure_ascii=False, default=str)


def record_audit_log(
    db: Session,
    *,
    actor: Any | None,
    action: str,
    resource_type: str,
    resource_id: Any | None = None,
    resource_name: str | None = None,
    org_id: int | None = None,
    status: str = "success",
    message: str | None = None,
    detail: Any | None = None,
    ip_address: str | None = None,
    commit: bool = True,
) -> AuditLog:
    log = AuditLog(
        actor_user_id=getattr(actor, "id", None),
        actor_username=getattr(actor, "username", None),
        actor_role=getattr(actor, "role", None),
        org_id=org_id if org_id is not None else getattr(actor, "org_id", None),
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        resource_name=resource_name,
        status=status,
        message=message,
        detail_json=_serialize_detail(detail),
        ip_address=ip_address,
    )
    db.add(log)
    if commit:
        db.commit()
        db.refresh(log)
    return log


def try_record_audit_log(db: Session, **kwargs: Any) -> AuditLog | None:
    try:
        return record_audit_log(db, **kwargs)
    except Exception:
        db.rollback()
        return None
