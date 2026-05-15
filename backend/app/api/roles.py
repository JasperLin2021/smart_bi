import json
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.audit import try_record_audit_log
from app.core.permissions import (
    ACTION_PERMISSION_KEYS,
    DATA_SCOPE_OWNER,
    MENU_PERMISSION_KEYS,
    ROLE_DISPLAY_NAMES,
    ROLE_LEVELS,
    VALID_ROLES,
    get_role_permission_template,
    has_action_permission,
    resolve_effective_permissions,
    require_action,
)
from app.db.session import get_db
from app.models.organization import Organization
from app.models.role import Role
from app.models.user import User
from app.schemas.role import RoleCreate, RoleUpdate

router = APIRouter(prefix="/roles", tags=["roles"])

_ROLE_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
_BUILTIN_ROLE_IDS = {
    "user": -1,
    "dept_admin": -2,
    "org_admin": -3,
    "super_admin": -4,
}
_DATA_SCOPES = {"owner", "org", "all"}


def _parse_permissions(raw_value: Any) -> dict[str, bool] | None:
    if raw_value is None:
        return None
    if isinstance(raw_value, str):
        if not raw_value.strip():
            return None
        try:
            raw_value = json.loads(raw_value)
        except json.JSONDecodeError:
            return None
    if isinstance(raw_value, dict):
        return {str(key): bool(value) for key, value in raw_value.items()}
    if isinstance(raw_value, list):
        return {str(item): True for item in raw_value}
    return None


def _dump_permissions(value: dict[str, bool] | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def _normalize_permissions(value: dict[str, bool] | None, keys: tuple[str, ...]) -> dict[str, bool]:
    parsed = _parse_permissions(value) or {}
    return {key: bool(parsed.get(key, False)) for key in keys}


def _role_template(menu_permissions: dict[str, bool], action_permissions: dict[str, bool], data_scope: str | None) -> dict[str, object]:
    return {
        "data_scope": data_scope or DATA_SCOPE_OWNER,
        "menu_permissions": menu_permissions,
        "action_permissions": action_permissions,
    }


def _builtin_role_to_out(role_code: str) -> dict:
    template = get_role_permission_template(role_code)
    return {
        "id": _BUILTIN_ROLE_IDS[role_code],
        "code": role_code,
        "name": ROLE_DISPLAY_NAMES.get(role_code, role_code),
        "description": "系统内置角色",
        "org_id": None,
        "org_name": None,
        "is_builtin": True,
        "data_scope": template["data_scope"],
        "template": template,
        "menu_permissions": template["menu_permissions"],
        "action_permissions": template["action_permissions"],
        "created_at": None,
        "updated_at": None,
    }


def _role_to_out(role: Role, db: Session) -> dict:
    menu_permissions = _normalize_permissions(_parse_permissions(role.menu_permissions), MENU_PERMISSION_KEYS)
    action_permissions = _normalize_permissions(_parse_permissions(role.action_permissions), ACTION_PERMISSION_KEYS)
    org_name = None
    if role.org_id:
        org = db.query(Organization).filter(Organization.id == role.org_id).first()
        org_name = org.name if org else None
    template = _role_template(menu_permissions, action_permissions, role.data_scope)
    return {
        "id": role.id,
        "code": role.code,
        "name": role.name,
        "description": role.description,
        "org_id": role.org_id,
        "org_name": org_name,
        "is_builtin": role.is_builtin,
        "data_scope": role.data_scope or DATA_SCOPE_OWNER,
        "template": template,
        "menu_permissions": menu_permissions,
        "action_permissions": action_permissions,
        "created_at": role.created_at,
        "updated_at": role.updated_at,
    }


def _role_query_for_actor(db: Session, current_user: User):
    query = db.query(Role).filter(Role.is_builtin.is_(False))
    if current_user.role == "super_admin":
        return query
    if current_user.org_id is None:
        return query.filter(Role.id == -1)
    return query.filter((Role.org_id == current_user.org_id) | (Role.org_id.is_(None)))


def _load_role_for_actor(db: Session, role_id: int, current_user: User) -> Role:
    if role_id <= 0:
        raise HTTPException(status_code=403, detail="内置角色不可编辑")
    role = _role_query_for_actor(db, current_user).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    return role


def _target_org_id(payload_org_id: int | None, current_user: User, db: Session) -> int | None:
    if current_user.role == "super_admin":
        target_org_id = payload_org_id
    else:
        if current_user.org_id is None:
            raise HTTPException(status_code=403, detail="当前用户未绑定企业")
        if payload_org_id is not None and payload_org_id != current_user.org_id:
            raise HTTPException(status_code=403, detail="只能管理本企业角色")
        target_org_id = current_user.org_id
    if target_org_id is not None and not db.query(Organization).filter(Organization.id == target_org_id).first():
        raise HTTPException(status_code=400, detail="企业不存在")
    return target_org_id


def _validate_role_code(code: str) -> str:
    normalized = code.strip().lower()
    if normalized in VALID_ROLES:
        raise HTTPException(status_code=400, detail="内置角色编码不可复用")
    if not _ROLE_CODE_RE.match(normalized):
        raise HTTPException(status_code=400, detail="角色编码需为小写字母、数字或下划线，并以字母开头")
    return normalized


def _validate_data_scope(data_scope: str | None, current_user: User) -> str:
    next_scope = data_scope or DATA_SCOPE_OWNER
    if next_scope not in _DATA_SCOPES:
        raise HTTPException(status_code=400, detail="数据范围无效")
    if current_user.role != "super_admin" and next_scope == "all":
        raise HTTPException(status_code=403, detail="无权创建全局数据范围角色")
    return next_scope


def _assert_permissions_not_exceed_actor(
    current_user: User,
    menu_permissions: dict[str, bool],
    action_permissions: dict[str, bool],
) -> None:
    if current_user.role == "super_admin":
        return
    effective = resolve_effective_permissions(current_user)
    actor_menu = effective["menu_permissions"]
    actor_action = effective["action_permissions"]
    for key, enabled in menu_permissions.items():
        if enabled and not actor_menu.get(key):
            raise HTTPException(status_code=403, detail=f"无权授予菜单权限: {key}")
    for key, enabled in action_permissions.items():
        if enabled and not actor_action.get(key):
            raise HTTPException(status_code=403, detail=f"无权授予操作权限: {key}")


def _duplicate_role_exists(db: Session, code: str, org_id: int | None, exclude_id: int | None = None) -> bool:
    query = db.query(Role).filter(Role.code == code)
    if org_id is None:
        query = query.filter(Role.org_id.is_(None))
    else:
        query = query.filter(Role.org_id == org_id)
    if exclude_id is not None:
        query = query.filter(Role.id != exclude_id)
    return query.first() is not None


def _custom_role_level(role: Role) -> int:
    action_permissions = _normalize_permissions(_parse_permissions(role.action_permissions), ACTION_PERMISSION_KEYS)
    if action_permissions.get("user.assign_org_admin"):
        return ROLE_LEVELS["org_admin"]
    if any(action_permissions.get(key) for key in ("user.create", "user.update", "department.read")):
        return ROLE_LEVELS["dept_admin"]
    return ROLE_LEVELS["user"]


def _assignable_role_codes(db: Session, current_user: User, target_org_id: int | None = None) -> set[str]:
    if current_user.role == "super_admin":
        codes = set(VALID_ROLES)
    elif current_user.role == "org_admin":
        codes = {"user", "dept_admin"}
        if has_action_permission(current_user, "user.assign_org_admin"):
            codes.add("org_admin")
    elif current_user.role == "dept_admin":
        codes = {"user"}
    else:
        codes = set()

    if current_user.role != "super_admin" and current_user.org_id is not None:
        org_id = current_user.org_id
    else:
        org_id = target_org_id
    for role in _role_query_for_actor(db, current_user).all():
        if role.org_id is not None and (org_id is None or role.org_id != org_id):
            continue
        if current_user.role == "super_admin" or _custom_role_level(role) <= ROLE_LEVELS["user"]:
            codes.add(role.code)
    return codes


def ensure_role_assignable(db: Session, current_user: User, role_code: str, target_org_id: int | None = None) -> None:
    if role_code not in _assignable_role_codes(db, current_user, target_org_id=target_org_id):
        raise HTTPException(status_code=403, detail="无权分配该角色")
    if role_code in VALID_ROLES:
        return
    exists_query = _role_query_for_actor(db, current_user).filter(Role.code == role_code)
    if target_org_id is None:
        exists_query = exists_query.filter(Role.org_id.is_(None))
    else:
        exists_query = exists_query.filter((Role.org_id == target_org_id) | (Role.org_id.is_(None)))
    exists = exists_query.first()
    if not exists:
        raise HTTPException(status_code=400, detail="角色不存在")


def role_label_for_code(db: Session, role_code: str, org_id: int | None = None) -> str:
    if role_code in ROLE_DISPLAY_NAMES:
        return ROLE_DISPLAY_NAMES[role_code]
    query = db.query(Role).filter(Role.code == role_code)
    if org_id is not None:
        query = query.filter((Role.org_id == org_id) | (Role.org_id.is_(None))).order_by(Role.org_id.desc())
    else:
        query = query.filter(Role.org_id.is_(None))
    role = query.first()
    return role.name if role else role_code


@router.get("", response_model=list[dict])
def list_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_action(current_user, "role.read")
    roles = [_builtin_role_to_out(role_code) for role_code in VALID_ROLES]
    custom_roles = [_role_to_out(role, db) for role in _role_query_for_actor(db, current_user).order_by(Role.org_id.asc(), Role.id.asc()).all()]
    return roles + custom_roles


@router.get("/assignable", response_model=list[dict])
def list_assignable_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_action(current_user, "user.create")
    assignable_codes = _assignable_role_codes(db, current_user, target_org_id=current_user.org_id)
    roles: list[dict] = []
    for role_code in VALID_ROLES:
        if role_code in assignable_codes:
            roles.append(_builtin_role_to_out(role_code))
    for role in _role_query_for_actor(db, current_user).order_by(Role.org_id.asc(), Role.id.asc()).all():
        if role.code in assignable_codes:
            roles.append(_role_to_out(role, db))
    return roles


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_role(
    payload: RoleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_action(current_user, "role.create")
    code = _validate_role_code(payload.code)
    org_id = _target_org_id(payload.org_id, current_user, db)
    if _duplicate_role_exists(db, code, org_id):
        raise HTTPException(status_code=400, detail="角色编码已存在")
    data_scope = _validate_data_scope(payload.data_scope, current_user)
    menu_permissions = _normalize_permissions(payload.menu_permissions, MENU_PERMISSION_KEYS)
    action_permissions = _normalize_permissions(payload.action_permissions, ACTION_PERMISSION_KEYS)
    _assert_permissions_not_exceed_actor(current_user, menu_permissions, action_permissions)

    role = Role(
        code=code,
        name=payload.name.strip(),
        description=payload.description,
        org_id=org_id,
        is_builtin=False,
        data_scope=data_scope,
        menu_permissions=_dump_permissions(menu_permissions),
        action_permissions=_dump_permissions(action_permissions),
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    try_record_audit_log(
        db,
        actor=current_user,
        action="role.create",
        resource_type="role",
        resource_id=role.id,
        resource_name=role.name,
        org_id=role.org_id,
        message="角色已创建",
        detail={"code": role.code},
    )
    return _role_to_out(role, db)


@router.put("/{role_id}", response_model=dict)
def update_role(
    role_id: int,
    payload: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_action(current_user, "role.update")
    role = _load_role_for_actor(db, role_id, current_user)

    if payload.code is not None:
        code = _validate_role_code(payload.code)
        if _duplicate_role_exists(db, code, role.org_id, exclude_id=role.id):
            raise HTTPException(status_code=400, detail="角色编码已存在")
        if code != role.code:
            assigned_query = db.query(User).filter(User.role == role.code)
            if role.org_id is not None:
                assigned_query = assigned_query.filter(User.org_id == role.org_id)
            if assigned_query.first():
                raise HTTPException(status_code=409, detail="该角色仍被用户使用，无法修改编码")
        role.code = code
    if payload.name is not None:
        role.name = payload.name.strip()
    if "description" in payload.model_fields_set:
        role.description = payload.description
    if payload.org_id is not None and current_user.role == "super_admin":
        role.org_id = _target_org_id(payload.org_id, current_user, db)
    if payload.data_scope is not None:
        role.data_scope = _validate_data_scope(payload.data_scope, current_user)

    menu_permissions = _normalize_permissions(_parse_permissions(role.menu_permissions), MENU_PERMISSION_KEYS)
    action_permissions = _normalize_permissions(_parse_permissions(role.action_permissions), ACTION_PERMISSION_KEYS)
    if payload.menu_permissions is not None:
        menu_permissions = _normalize_permissions(payload.menu_permissions, MENU_PERMISSION_KEYS)
    if payload.action_permissions is not None:
        action_permissions = _normalize_permissions(payload.action_permissions, ACTION_PERMISSION_KEYS)
    _assert_permissions_not_exceed_actor(current_user, menu_permissions, action_permissions)
    role.menu_permissions = _dump_permissions(menu_permissions)
    role.action_permissions = _dump_permissions(action_permissions)

    db.commit()
    db.refresh(role)
    try_record_audit_log(
        db,
        actor=current_user,
        action="role.update",
        resource_type="role",
        resource_id=role.id,
        resource_name=role.name,
        org_id=role.org_id,
        message="角色已更新",
        detail={"fields": list(payload.model_dump(exclude_unset=True).keys())},
    )
    return _role_to_out(role, db)


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_action(current_user, "role.delete")
    role = _load_role_for_actor(db, role_id, current_user)
    assigned_query = db.query(User).filter(User.role == role.code)
    if role.org_id is not None:
        assigned_query = assigned_query.filter(User.org_id == role.org_id)
    if assigned_query.first():
        raise HTTPException(status_code=409, detail="该角色仍被用户使用，无法删除")
    role_id_value = role.id
    role_name = role.name
    role_org_id = role.org_id
    db.delete(role)
    db.commit()
    try_record_audit_log(
        db,
        actor=current_user,
        action="role.delete",
        resource_type="role",
        resource_id=role_id_value,
        resource_name=role_name,
        org_id=role_org_id,
        message="角色已删除",
    )
