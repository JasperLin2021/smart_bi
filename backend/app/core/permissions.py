import json
from copy import deepcopy
from typing import Any

from fastapi import HTTPException, status

from app.models.user import User


DATA_SCOPE_ALL = "all"
DATA_SCOPE_ORG = "org"
DATA_SCOPE_OWNER = "owner"

# ─── Permission catalog ───────────────────────────────────────────────────────
# Each entry: (code, display_name, type, group)
PERMISSION_CATALOG = [
    # Menu permissions
    ("dashboard.view",        "工作台 Dashboard",   "menu", "工作台"),
    ("smart_query.view",      "智能问数",           "menu", "工作台"),
    ("action_items.view",     "行动闭环",           "menu", "工作台"),
    ("datasource.view",       "数据源管理",         "menu", "数据接入"),
    ("dataset.view",          "数据集开发",         "menu", "数据接入"),
    ("data_link.view",        "数据接入（连接器）", "menu", "数据接入"),
    ("olap.view",             "数据平台",           "menu", "数据接入"),
    ("catalog.view",          "数据目录",           "menu", "数据接入"),
    ("dashboard_center.view", "看板中心",           "menu", "BI分析"),
    ("goview.view",           "大屏中心",           "menu", "BI分析"),
    ("metric.view",           "可信指标",           "menu", "BI分析"),
    ("alert.view",            "预警管理",           "menu", "BI分析"),
    ("admin_console.view",    "系统管理入口",       "menu", "系统管理"),
    ("llm_settings.view",     "大模型配置",         "menu", "系统管理"),
    # Action permissions
    ("user.read",             "查看用户",           "action", "用户管理"),
    ("user.create",           "创建用户",           "action", "用户管理"),
    ("user.update",           "编辑用户",           "action", "用户管理"),
    ("user.delete",           "删除用户",           "action", "用户管理"),
    ("user.permission.update","修改用户权限",       "action", "用户管理"),
    ("organization.read",     "查看企业信息",       "action", "企业管理"),
    ("organization.create",   "创建企业",           "action", "企业管理"),
    ("organization.update",   "编辑企业",           "action", "企业管理"),
    ("organization.delete",   "删除企业",           "action", "企业管理"),
    ("datasource.read",       "查看数据源",         "action", "数据源"),
    ("datasource.create",     "创建数据源",         "action", "数据源"),
    ("datasource.update",     "编辑数据源",         "action", "数据源"),
    ("datasource.delete",     "删除数据源",         "action", "数据源"),
    ("metric.read",           "查看指标",           "action", "指标"),
    ("metric.create",         "创建指标",           "action", "指标"),
    ("metric.update",         "编辑指标",           "action", "指标"),
    ("metric.delete",         "删除指标",           "action", "指标"),
    ("metric.certify",        "认证指标",           "action", "指标"),
    ("alert.read",            "查看预警",           "action", "预警"),
    ("alert.create",          "创建预警",           "action", "预警"),
    ("alert.update",          "编辑预警",           "action", "预警"),
    ("alert.delete",          "删除预警",           "action", "预警"),
    ("catalog.read",          "查看数据目录",       "action", "数据目录"),
    ("catalog.update",        "编辑数据目录",       "action", "数据目录"),
    ("dashboard.read",        "查看看板",           "action", "看板"),
    ("dashboard.create",      "创建看板",           "action", "看板"),
    ("dashboard.update",      "编辑看板",           "action", "看板"),
    ("dashboard.delete",      "删除看板",           "action", "看板"),
    ("dashboard.publish",     "发布看板",           "action", "看板"),
    ("goview.read",           "查看大屏",           "action", "大屏"),
    ("goview.design",         "设计大屏",           "action", "大屏"),
    ("llm_settings.read",     "查看大模型配置",     "action", "系统配置"),
    ("llm_settings.update",   "修改大模型配置",     "action", "系统配置"),
]

MENU_PERMISSION_KEYS = tuple(c for c, *_ in PERMISSION_CATALOG if _ and _[1] == "menu")
ACTION_PERMISSION_KEYS = tuple(c for c, *_ in PERMISSION_CATALOG if _ and _[1] == "action")


def get_permission_catalog_tree() -> list[dict]:
    """Return permission catalog as grouped tree for UI rendering."""
    groups: dict[str, dict] = {}
    for code, name, ptype, group in PERMISSION_CATALOG:
        key = f"{ptype}:{group}"
        if key not in groups:
            groups[key] = {"type": ptype, "group": group, "permissions": []}
        groups[key]["permissions"].append({"code": code, "name": name})
    return list(groups.values())


def _permission_map(enabled_keys: tuple[str, ...], all_keys: tuple[str, ...]) -> dict[str, bool]:
    enabled = set(enabled_keys)
    return {key: key in enabled for key in all_keys}


# ─── Role permission templates ────────────────────────────────────────────────

ROLE_PERMISSION_TEMPLATES: dict[str, dict[str, Any]] = {
    "user": {
        "data_scope": DATA_SCOPE_OWNER,
        "menu_permissions": _permission_map(
            (
                "dashboard.view",
                "smart_query.view",
                "action_items.view",
                "datasource.view",
                "metric.view",
                "alert.view",
                "catalog.view",
                "dashboard_center.view",
                "goview.view",
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
                "goview.read",
            ),
            ACTION_PERMISSION_KEYS,
        ),
    },
    "dept_admin": {
        "data_scope": DATA_SCOPE_ORG,
        "menu_permissions": _permission_map(
            (
                "dashboard.view",
                "smart_query.view",
                "action_items.view",
                "datasource.view",
                "dataset.view",
                "catalog.view",
                "dashboard_center.view",
                "goview.view",
                "metric.view",
                "alert.view",
                "admin_console.view",
            ),
            MENU_PERMISSION_KEYS,
        ),
        "action_permissions": _permission_map(
            (
                "user.read",
                "datasource.read",
                "metric.read",
                "metric.create",
                "metric.update",
                "alert.read",
                "alert.create",
                "alert.update",
                "catalog.read",
                "catalog.update",
                "dashboard.read",
                "dashboard.create",
                "dashboard.update",
                "dashboard.publish",
                "goview.read",
                "goview.design",
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
                "action_items.view",
                "datasource.view",
                "dataset.view",
                "data_link.view",
                "olap.view",
                "catalog.view",
                "dashboard_center.view",
                "goview.view",
                "metric.view",
                "alert.view",
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
                "user.permission.update",
                "datasource.read",
                "datasource.create",
                "datasource.update",
                "datasource.delete",
                "metric.read",
                "metric.create",
                "metric.update",
                "metric.delete",
                "metric.certify",
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
                "goview.read",
                "goview.design",
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

VALID_ROLES = ("user", "dept_admin", "org_admin", "super_admin")

ROLE_DISPLAY_NAMES = {
    "user": "普通用户",
    "dept_admin": "部门管理员",
    "org_admin": "企业管理员",
    "super_admin": "超级管理员",
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
    if user.role != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要超级管理员权限")
    return user


def require_org_admin_or_above(user: User) -> User:
    """org_admin and super_admin can do user/org management."""
    if user.role not in ("org_admin", "super_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要企业管理员或以上权限")
    return user


def require_dept_admin_or_above(user: User) -> User:
    """dept_admin, org_admin, super_admin can manage BI assets and action items."""
    if user.role not in ("dept_admin", "org_admin", "super_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要部门管理员或以上权限")
    return user


def is_admin_role(role: str | None) -> bool:
    return role in ("dept_admin", "org_admin", "super_admin")


def check_org_access(user: User, org_id: int) -> bool:
    if user.role == "super_admin":
        return True
    return user.org_id == org_id


def get_accessible_org_ids(user: User) -> list[int] | None:
    if user.role == "super_admin":
        return None
    return [user.org_id] if user.org_id else []
