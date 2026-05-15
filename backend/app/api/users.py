import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.auth import get_current_user
from app.api.roles import ensure_role_assignable, role_label_for_code
from app.core.audit import try_record_audit_log
from app.core.permissions import (
    ROLE_DISPLAY_NAMES, VALID_ROLES,
    get_permission_catalog_tree, get_role_permission_template,
    has_action_permission, require_action,
)
from app.core.safe_delete import assert_user_can_delete
from app.core.security import get_password_hash
from app.db.session import get_db
from app.models.organization import Department, Organization
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserOut

router = APIRouter(prefix="/users", tags=["users"])


def _parse_permissions(raw_value: str | None) -> dict[str, bool] | None:
    if not raw_value:
        return None
    try:
        return json.loads(raw_value)
    except (json.JSONDecodeError, TypeError):
        return None


def _dump_permissions(value: dict[str, bool] | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def _user_to_out(user: User, db: Session) -> dict:
    org_name = None
    if user.org_id:
        org = db.query(Organization).filter(Organization.id == user.org_id).first()
        if org:
            org_name = org.name
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "role_label": role_label_for_code(db, user.role, user.org_id),
        "department_id": getattr(user, "department_id", None),
        "department": getattr(user, "department", None),
        "org_id": user.org_id,
        "org_name": org_name,
        "data_scope": user.data_scope,
        "permission_override_enabled": user.permission_override_enabled,
        "menu_permissions": _parse_permissions(user.menu_permissions),
        "action_permissions": _parse_permissions(user.action_permissions),
    }


def _resolve_department(
    db: Session,
    *,
    org_id: int | None,
    department_id: int | None,
) -> Department | None:
    if department_id is None:
        return None
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(status_code=400, detail="部门不存在")
    if org_id is not None and department.org_id != org_id:
        raise HTTPException(status_code=400, detail="部门不属于所选企业")
    return department


def _department_subtree_ids(db: Session, org_id: int, department_id: int) -> set[int]:
    scoped_ids: set[int] = {department_id}
    frontier = [department_id]
    while frontier:
        rows = (
            db.query(Department.id)
            .filter(Department.org_id == org_id, Department.parent_id.in_(frontier))
            .all()
        )
        frontier = [row[0] for row in rows if row[0] not in scoped_ids]
        scoped_ids.update(frontier)
    return scoped_ids


def _managed_department_ids(db: Session, current_user: User) -> set[int] | None:
    if current_user.role != "dept_admin":
        return None
    if current_user.org_id is None or current_user.department_id is None:
        return set()
    return _department_subtree_ids(db, current_user.org_id, current_user.department_id)


def _scoped_users_query(db: Session, current_user: User):
    query = db.query(User)
    if current_user.role == "super_admin":
        return query
    if current_user.org_id is None:
        raise HTTPException(status_code=403, detail="当前用户未绑定企业")
    query = query.filter(User.org_id == current_user.org_id)
    if current_user.role == "dept_admin":
        department_ids = _managed_department_ids(db, current_user) or set()
        if not department_ids:
            return query.filter(User.id == -1)
        query = query.filter(User.department_id.in_(department_ids))
    return query


def _ensure_user_scope(db: Session, current_user: User, target_user: User) -> None:
    if current_user.role == "super_admin":
        return
    if current_user.org_id is None or target_user.org_id != current_user.org_id:
        raise HTTPException(status_code=403, detail="无权访问此用户")
    if current_user.role == "dept_admin":
        department_ids = _managed_department_ids(db, current_user) or set()
        if target_user.department_id not in department_ids:
            raise HTTPException(status_code=403, detail="只能管理本部门及下级部门用户")


def _ensure_department_scope(db: Session, current_user: User, department_id: int | None) -> None:
    if current_user.role != "dept_admin":
        return
    department_ids = _managed_department_ids(db, current_user) or set()
    if department_id is None or department_id not in department_ids:
        raise HTTPException(status_code=403, detail="只能管理本部门及下级部门用户")


def _ensure_target_role_manageable(current_user: User, target_role: str) -> None:
    if current_user.role == "super_admin":
        return
    if target_role == "super_admin":
        raise HTTPException(status_code=403, detail="无权管理超级管理员")
    if target_role == "org_admin" and not has_action_permission(current_user, "user.assign_org_admin"):
        raise HTTPException(status_code=403, detail="无权管理企业管理员")


def _payload_changes_permission_fields(payload: UserUpdate) -> bool:
    return bool({"permission_override_enabled", "menu_permissions", "action_permissions"} & payload.model_fields_set)


@router.get("", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_action(current_user, "user.read")
    users = _scoped_users_query(db, current_user).all()
    return [_user_to_out(u, db) for u in users]


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_action(current_user, "user.create")
    if payload.permission_override_enabled or payload.menu_permissions is not None or payload.action_permissions is not None:
        require_action(current_user, "user.permission.update")
    
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")

    target_org_id = payload.org_id
    if current_user.role != "super_admin":
        if current_user.org_id is None:
            raise HTTPException(status_code=403, detail="当前用户未绑定企业")
        if target_org_id and target_org_id != current_user.org_id:
            raise HTTPException(status_code=403, detail="只能创建本企业用户")
        target_org_id = current_user.org_id

    department = _resolve_department(db, org_id=target_org_id, department_id=payload.department_id)
    if department and target_org_id is None:
        target_org_id = department.org_id
    _ensure_department_scope(db, current_user, department.id if department else None)
    ensure_role_assignable(db, current_user, payload.role, target_org_id=target_org_id)

    user = User(
        username=payload.username,
        hashed_password=get_password_hash(payload.password),
        role=payload.role,
        org_id=target_org_id,
        department_id=department.id if department else None,
        department=department.name if department else getattr(payload, "department", None),
        data_scope=payload.data_scope,
        permission_override_enabled=payload.permission_override_enabled,
        menu_permissions=_dump_permissions(payload.menu_permissions),
        action_permissions=_dump_permissions(payload.action_permissions),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    try_record_audit_log(
        db,
        actor=current_user,
        action="user.create",
        resource_type="user",
        resource_id=user.id,
        resource_name=user.username,
        org_id=user.org_id,
        message="用户已创建",
        detail={"role": user.role},
    )
    return _user_to_out(user, db)


@router.get("/assignable", response_model=list[dict])
def list_assignable_users_inline(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return users that current user can assign action items to, grouped by dept."""
    if current_user.role == "super_admin":
        users = db.query(User).all()
    else:
        users = _scoped_users_query(db, current_user).all()

    dept_map: dict[str, list[dict]] = {}
    for u in users:
        dept = getattr(u, "department", None) or "未分配部门"
        if dept not in dept_map:
            dept_map[dept] = []
        dept_map[dept].append({
            "id": u.id,
            "username": u.username,
            "role": u.role,
            "role_label": role_label_for_code(db, u.role, u.org_id),
            "department_id": getattr(u, "department_id", None),
            "department": dept,
        })

    return [
        {"department": dept, "users": sorted(members, key=lambda x: x["username"])}
        for dept, members in sorted(dept_map.items())
    ]


@router.get("/permissions/catalog")
def get_permissions_catalog_inline(current_user: User = Depends(get_current_user)):
    """Return the full permission catalog tree for the permission management UI."""
    require_action(current_user, "user.read")
    return {
        "catalog": get_permission_catalog_tree(),
        "roles": [
            {
                "code": role,
                "name": ROLE_DISPLAY_NAMES.get(role, role),
                "template": get_role_permission_template(role),
                "is_builtin": True,
            }
            for role in VALID_ROLES
        ],
    }


@router.get("/{user_id}", response_model=UserOut)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_action(current_user, "user.read")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    _ensure_user_scope(db, current_user, user)
    return _user_to_out(user, db)


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_action(current_user, "user.update")
    if _payload_changes_permission_fields(payload):
        require_action(current_user, "user.permission.update")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    _ensure_user_scope(db, current_user, user)
    _ensure_target_role_manageable(current_user, user.role)

    next_org_id = user.org_id
    if payload.org_id is not None:
        if current_user.role != "super_admin":
            raise HTTPException(status_code=403, detail="只能修改本企业用户")
        next_org_id = payload.org_id
    if current_user.role != "super_admin" and next_org_id != current_user.org_id:
        raise HTTPException(status_code=403, detail="只能修改本企业用户")

    next_department = None
    next_department_id = user.department_id
    if "department_id" in payload.model_fields_set:
        next_department = _resolve_department(db, org_id=next_org_id, department_id=payload.department_id)
        next_department_id = next_department.id if next_department else None
        _ensure_department_scope(db, current_user, next_department_id)
    elif payload.org_id is not None and user.department_id is not None:
        existing_department = _resolve_department(db, org_id=None, department_id=user.department_id)
        if existing_department and existing_department.org_id != next_org_id:
            next_department_id = None
            next_department = None
        else:
            next_department = existing_department
        _ensure_department_scope(db, current_user, next_department_id)
    else:
        _ensure_department_scope(db, current_user, user.department_id)

    if payload.role is not None:
        ensure_role_assignable(db, current_user, payload.role, target_org_id=next_org_id)
    
    if payload.username is not None:
        if db.query(User).filter(User.username == payload.username, User.id != user_id).first():
            raise HTTPException(status_code=400, detail="用户名已存在")
        user.username = payload.username
    if payload.password is not None:
        user.hashed_password = get_password_hash(payload.password)
    if payload.role is not None:
        user.role = payload.role
    if payload.org_id is not None and current_user.role == "super_admin":
        user.org_id = next_org_id

    if "department_id" in payload.model_fields_set:
        user.department_id = next_department_id
        user.department = next_department.name if next_department else None
    elif payload.org_id is not None and user.department_id is not None:
        user.department_id = next_department_id
        user.department = next_department.name if next_department else None

    if "department" in payload.model_fields_set and payload.department is not None and user.department_id is None:
        user.department = payload.department
    if payload.data_scope is not None:
        user.data_scope = payload.data_scope
    if payload.permission_override_enabled is not None:
        user.permission_override_enabled = payload.permission_override_enabled
    if payload.menu_permissions is not None:
        user.menu_permissions = _dump_permissions(payload.menu_permissions)
    if payload.action_permissions is not None:
        user.action_permissions = _dump_permissions(payload.action_permissions)
    
    db.commit()
    db.refresh(user)
    try_record_audit_log(
        db,
        actor=current_user,
        action="user.update",
        resource_type="user",
        resource_id=user.id,
        resource_name=user.username,
        org_id=user.org_id,
        message="用户已更新",
        detail={"fields": list(payload.model_dump(exclude_unset=True).keys())},
    )
    return _user_to_out(user, db)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_action(current_user, "user.delete")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    _ensure_user_scope(db, current_user, user)
    _ensure_target_role_manageable(current_user, user.role)
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除自己")
    assert_user_can_delete(db, user)
    user_id_value = user.id
    username = user.username
    user_org_id = user.org_id
    db.delete(user)
    db.commit()
    try_record_audit_log(
        db,
        actor=current_user,
        action="user.delete",
        resource_type="user",
        resource_id=user_id_value,
        resource_name=username,
        org_id=user_org_id,
        message="用户已删除",
    )
