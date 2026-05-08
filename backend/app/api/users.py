import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.auth import get_current_user
from app.core.audit import try_record_audit_log
from app.core.permissions import (
    require_org_admin_or_above, ROLE_DISPLAY_NAMES, VALID_ROLES,
    get_permission_catalog_tree, get_role_permission_template,
)
from app.core.safe_delete import assert_user_can_delete
from app.core.security import get_password_hash
from app.db.session import get_db
from app.models.organization import Organization
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
        "role_label": ROLE_DISPLAY_NAMES.get(user.role, user.role),
        "department": getattr(user, "department", None),
        "org_id": user.org_id,
        "org_name": org_name,
        "data_scope": user.data_scope,
        "permission_override_enabled": user.permission_override_enabled,
        "menu_permissions": _parse_permissions(user.menu_permissions),
        "action_permissions": _parse_permissions(user.action_permissions),
    }


@router.get("", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_org_admin_or_above(current_user)
    if current_user.role == "super_admin":
        users = db.query(User).all()
    else:
        users = db.query(User).filter(User.org_id == current_user.org_id).all()
    return [_user_to_out(u, db) for u in users]


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_org_admin_or_above(current_user)
    
    # org_admin can only create users in their own org
    if current_user.role == "org_admin":
        if payload.org_id and payload.org_id != current_user.org_id:
            raise HTTPException(status_code=403, detail="只能创建本企业用户")
        payload.org_id = current_user.org_id
        # org_admin cannot create super_admin
        if payload.role == "super_admin":
            raise HTTPException(status_code=403, detail="无权创建超级管理员")
    
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")

    user = User(
        username=payload.username,
        hashed_password=get_password_hash(payload.password),
        role=payload.role,
        org_id=payload.org_id,
        department=getattr(payload, "department", None),
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
        users = db.query(User).filter(User.org_id == current_user.org_id).all()

    dept_map: dict[str, list[dict]] = {}
    for u in users:
        dept = getattr(u, "department", None) or "未分配部门"
        if dept not in dept_map:
            dept_map[dept] = []
        dept_map[dept].append({
            "id": u.id,
            "username": u.username,
            "role": u.role,
            "role_label": ROLE_DISPLAY_NAMES.get(u.role, u.role),
            "department": dept,
        })

    return [
        {"department": dept, "users": sorted(members, key=lambda x: x["username"])}
        for dept, members in sorted(dept_map.items())
    ]


@router.get("/permissions/catalog")
def get_permissions_catalog_inline(current_user: User = Depends(get_current_user)):
    """Return the full permission catalog tree for the permission management UI."""
    require_org_admin_or_above(current_user)
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
    require_org_admin_or_above(current_user)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if current_user.role != "super_admin" and user.org_id != current_user.org_id:
        raise HTTPException(status_code=403, detail="无权访问此用户")
    return _user_to_out(user, db)


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_org_admin_or_above(current_user)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if current_user.role != "super_admin" and user.org_id != current_user.org_id:
        raise HTTPException(status_code=403, detail="无权修改此用户")
    
    if payload.username is not None:
        if db.query(User).filter(User.username == payload.username, User.id != user_id).first():
            raise HTTPException(status_code=400, detail="用户名已存在")
        user.username = payload.username
    if payload.password is not None:
        user.hashed_password = get_password_hash(payload.password)
    if payload.role is not None:
        if current_user.role == "org_admin" and payload.role == "super_admin":
            raise HTTPException(status_code=403, detail="无权设置超级管理员")
        user.role = payload.role
    if payload.org_id is not None and current_user.role == "super_admin":
        user.org_id = payload.org_id
    if hasattr(payload, "department") and payload.department is not None:
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
    require_org_admin_or_above(current_user)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if current_user.role != "super_admin" and user.org_id != current_user.org_id:
        raise HTTPException(status_code=403, detail="无权删除此用户")
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


