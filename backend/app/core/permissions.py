import json
from copy import deepcopy
from typing import Any

from fastapi import HTTPException, status

from app.models.user import User


DATA_SCOPE_ALL = "all"
DATA_SCOPE_ORG = "org"
DATA_SCOPE_OWNER = "owner"

MENU_PERMISSION_KEYS = (
    "dashboard.view",
    "smart_query.view",
    "datasource.view",
    "metric.view",
    "alert.view",
    "catalog.view",
    "dashboard_center.view",
    "admin_console.view",
    "llm_settings.view",
)

ACTION_PERMISSION_KEYS = (
    "organization.read",
    "organization.create",
    "organization.update",
    "organization.delete",
    "user.read",
    "user.create",
    "user.update",
    "user.delete",
    "user.permission.update",
    "datasource.read",
    "datasource.create",
    "datasource.update",
    "datasource.delete",
    "metric.read",
    "metric.create",
    "metric.update",
    "metric.delete",
    "alert.read",
    "alert.create",
    "alert.update",
    "alert.delete",
    "catalog.read",
    "catalog.update",
    "dashboard.read",
    "dashboard.create",
    "dashboard.update",
    "dashboard.delete",
    "dashboard.publish",
    "llm_settings.read",
    "llm_settings.update",
)


def _permission_map(enabled_keys: tuple[str, ...], all_keys: tuple[str, ...]) -> dict[str, bool]:
    enabled = set(enabled_keys)
    return {key: key in enabled for key in all_keys}


ROLE_PERMISSION_TEMPLATES: dict[str, dict[str, Any]] = {
    "user": {
        "data_scope": DATA_SCOPE_OWNER,
        "menu_permissions": _permission_map(
            (
                "dashboard.view",
                "smart_query.view",
                "datasource.view",
                "metric.view",
                "alert.view",
                "catalog.view",
                "dashboard_center.view",
            ),
            MENU_PERMISSION_KEYS,
        ),
        "action_permissions": _permission_map(
            (
                "datasource.read",
                "metric.read",
                "alert.read",
                "catalog.read",
                "dashboard.read",
            ),
            ACTION_PERMISSION_KEYS,
        ),
    },
    "org_admin": {
        "data_scope": DATA_SCOPE_ORG,
        "menu_permissions": _permission_map(
            (
                "dashboard.view",
                "smart_query.view",
                "datasource.view",
                "metric.view",
                "alert.view",
                "catalog.view",
                "dashboard_center.view",
                "admin_console.view",
            ),
            MENU_PERMISSION_KEYS,
        ),
        "action_permissions": _permission_map(
            (
                "organization.read",
                "user.read",
                "user.create",
                "user.update",
                "user.delete",
                "datasource.read",
                "datasource.create",
                "datasource.update",
                "datasource.delete",
                "metric.read",
                "metric.create",
                "metric.update",
                "metric.delete",
                "alert.read",
                "alert.create",
                "alert.update",
                "alert.delete",
                "catalog.read",
                "catalog.update",
                "dashboard.read",
                "dashboard.create",
                "dashboard.update",
                "dashboard.delete",
                "dashboard.publish",
                "user.permission.update",
            ),
            ACTION_PERMISSION_KEYS,
        ),
    },
    "super_admin": {
        "data_scope": DATA_SCOPE_ALL,
        "menu_permissions": _permission_map(MENU_PERMISSION_KEYS, MENU_PERMISSION_KEYS),
        "action_permissions": _permission_map(ACTION_PERMISSION_KEYS, ACTION_PERMISSION_KEYS),
    },
}


def get_role_permission_template(role: str | None) -> dict[str, Any]:
    template = ROLE_PERMISSION_TEMPLATES.get(role or "", ROLE_PERMISSION_TEMPLATES["user"])
    return deepcopy(template)


def _parse_permission_map(raw_value: Any) -> dict[str, bool] | None:
    if raw_value is None:
        return None
    if isinstance(raw_value, str):
        text = raw_value.strip()
        if not text:
            return None
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return None
    else:
        parsed = raw_value

    if parsed is None:
        return None
    if isinstance(parsed, dict):
        return {str(key): bool(value) for key, value in parsed.items()}
    if isinstance(parsed, list):
        return {str(item): True for item in parsed}
    return {str(parsed): True}


def _merge_permission_overlay(base: dict[str, bool], overlay: dict[str, bool] | None) -> dict[str, bool]:
    merged = deepcopy(base)
    if not overlay:
        return merged
    for key, value in overlay.items():
        merged[key] = bool(value)
    return merged


def resolve_effective_permissions(user: User) -> dict[str, Any]:
    role_template = get_role_permission_template(user.role)
    if user.role == "super_admin":
        return role_template

    if not getattr(user, "permission_override_enabled", False):
        return role_template

    data_scope = getattr(user, "data_scope", None)
    return {
        "data_scope": role_template["data_scope"] if data_scope is None else str(data_scope),
        "menu_permissions": _merge_permission_overlay(
            role_template["menu_permissions"],
            _parse_permission_map(getattr(user, "menu_permissions", None)),
        ),
        "action_permissions": _merge_permission_overlay(
            role_template["action_permissions"],
            _parse_permission_map(getattr(user, "action_permissions", None)),
        ),
    }


def has_menu_permission(user: User, permission_key: str) -> bool:
    effective = resolve_effective_permissions(user)
    return bool(effective["menu_permissions"].get(permission_key))


def has_action_permission(user: User, permission_key: str) -> bool:
    effective = resolve_effective_permissions(user)
    return bool(effective["action_permissions"].get(permission_key))


def require_menu(user: User, permission_key: str) -> User:
    if not has_menu_permission(user, permission_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"需要菜单权限: {permission_key}",
        )
    return user


def require_action(user: User, permission_key: str) -> User:
    if not has_action_permission(user, permission_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"需要操作权限: {permission_key}",
        )
    return user


def require_super_admin(user: User) -> User:
    """Raises 403 if not super_admin"""
    if user.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要超级管理员权限"
        )
    return user


def require_org_admin_or_above(user: User) -> User:
    """Raises 403 if role is 'user'"""
    if user.role not in ("org_admin", "super_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要企业管理员或以上权限"
        )
    return user


def check_org_access(user: User, org_id: int) -> bool:
    """Returns True if user can access this org's resources"""
    if user.role == "super_admin":
        return True
    return user.org_id == org_id


def get_accessible_org_ids(user: User) -> list[int] | None:
    """Returns list of org_ids user can access, or None for all (super_admin)"""
    if user.role == "super_admin":
        return None  # All orgs
    return [user.org_id] if user.org_id else []
