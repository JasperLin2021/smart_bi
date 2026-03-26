from fastapi import HTTPException, status
from app.models.user import User


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
