from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class RoleBase(BaseModel):
    code: Optional[str] = Field(default=None, min_length=2, max_length=64)
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    description: Optional[str] = None
    org_id: Optional[int] = None
    data_scope: Optional[str] = None
    menu_permissions: Optional[dict[str, bool]] = None
    action_permissions: Optional[dict[str, bool]] = None


class RoleCreate(RoleBase):
    code: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=1, max_length=128)


class RoleUpdate(RoleBase):
    pass


class RoleOut(BaseModel):
    id: int
    code: str
    name: str
    description: Optional[str] = None
    org_id: Optional[int] = None
    org_name: Optional[str] = None
    is_builtin: bool
    data_scope: Optional[str] = None
    template: dict[str, object]
    menu_permissions: dict[str, bool]
    action_permissions: dict[str, bool]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
