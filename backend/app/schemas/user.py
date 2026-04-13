from typing import Optional
from pydantic import BaseModel


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "user"  # user | org_admin | super_admin
    org_id: Optional[int] = None
    data_scope: Optional[str] = None
    permission_override_enabled: bool = False
    menu_permissions: Optional[dict[str, bool]] = None
    action_permissions: Optional[dict[str, bool]] = None


class UserUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    org_id: Optional[int] = None
    data_scope: Optional[str] = None
    permission_override_enabled: Optional[bool] = None
    menu_permissions: Optional[dict[str, bool]] = None
    action_permissions: Optional[dict[str, bool]] = None


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    org_id: Optional[int] = None
    org_name: Optional[str] = None
    data_scope: Optional[str] = None
    permission_override_enabled: Optional[bool] = None
    menu_permissions: Optional[dict[str, bool]] = None
    action_permissions: Optional[dict[str, bool]] = None

    class Config:
        from_attributes = True
