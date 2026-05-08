import json
import secrets
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.core.wechat_work import WECHAT_WORK_PROVIDER, WechatWorkUser
from app.models.integration import ExternalIdentity, ExternalOrgBinding, ExternalPermissionMapping
from app.models.user import User

VALID_EXTERNAL_ROLES = {"user", "org_admin"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _dump_permissions(raw_value: str | dict[str, bool] | None) -> str | None:
    if raw_value is None:
        return None
    if isinstance(raw_value, str):
        return raw_value
    return json.dumps(raw_value, ensure_ascii=False)


def _department_ids(external_user: WechatWorkUser) -> list[str]:
    return [str(item) for item in (external_user.department_ids or [])]


def _find_org_binding(db: Session, corp_id: str) -> ExternalOrgBinding:
    binding = (
        db.query(ExternalOrgBinding)
        .filter(
            ExternalOrgBinding.provider == WECHAT_WORK_PROVIDER,
            ExternalOrgBinding.external_corp_id == corp_id,
        )
        .first()
    )
    if not binding:
        raise HTTPException(status_code=403, detail="企业微信 CorpID 未绑定本地企业")
    return binding


def _find_best_mapping(
    db: Session,
    *,
    corp_id: str,
    org_id: int,
    department_ids: list[str],
) -> ExternalPermissionMapping | None:
    if not department_ids:
        return None
    mappings = (
        db.query(ExternalPermissionMapping)
        .filter(
            ExternalPermissionMapping.provider == WECHAT_WORK_PROVIDER,
            ExternalPermissionMapping.external_corp_id == corp_id,
            ExternalPermissionMapping.org_id == org_id,
            ExternalPermissionMapping.enabled == True,  # noqa: E712
        )
        .order_by(ExternalPermissionMapping.priority.asc(), ExternalPermissionMapping.id.asc())
        .all()
    )
    department_set = set(department_ids)
    for mapping in mappings:
        if mapping.role not in VALID_EXTERNAL_ROLES:
            continue
        if str(mapping.external_department_id) in department_set:
            return mapping
    return None


def apply_external_department_mapping(
    db: Session,
    user: User,
    *,
    corp_id: str,
    department_ids: list[str],
) -> None:
    mapping = _find_best_mapping(db, corp_id=corp_id, org_id=user.org_id, department_ids=department_ids)
    if not mapping:
        user.role = "user"
        user.data_scope = None
        user.permission_override_enabled = False
        user.menu_permissions = None
        user.action_permissions = None
        return

    user.role = mapping.role
    user.data_scope = mapping.data_scope
    user.permission_override_enabled = True
    user.menu_permissions = _dump_permissions(mapping.menu_permissions)
    user.action_permissions = _dump_permissions(mapping.action_permissions)


def upsert_wechat_work_user(
    db: Session,
    *,
    corp_id: str,
    external_user: WechatWorkUser,
) -> User:
    binding = _find_org_binding(db, corp_id)
    department_ids = _department_ids(external_user)
    identity = (
        db.query(ExternalIdentity)
        .filter(
            ExternalIdentity.provider == WECHAT_WORK_PROVIDER,
            ExternalIdentity.external_corp_id == corp_id,
            ExternalIdentity.external_user_id == external_user.user_id,
        )
        .first()
    )

    if identity:
        user = db.query(User).filter(User.id == identity.user_id).first()
        if not user:
            raise HTTPException(status_code=401, detail="企微身份绑定的用户不存在")
    else:
        username = f"ww:{corp_id}:{external_user.user_id}"
        user = db.query(User).filter(User.username == username).first()
        if not user:
            user = User(
                username=username,
                hashed_password=get_password_hash(secrets.token_urlsafe(32)),
                role="user",
                org_id=binding.org_id,
            )
            db.add(user)
            db.flush()
        identity = ExternalIdentity(
            provider=WECHAT_WORK_PROVIDER,
            external_corp_id=corp_id,
            external_user_id=external_user.user_id,
            user_id=user.id,
        )
        db.add(identity)

    user.org_id = binding.org_id
    identity.display_name = external_user.name
    identity.email = external_user.email
    identity.mobile = external_user.mobile
    identity.department_ids_json = json.dumps(department_ids, ensure_ascii=False)
    identity.last_login_at = _utcnow()
    apply_external_department_mapping(db, user, corp_id=corp_id, department_ids=department_ids)
    db.flush()
    return user
