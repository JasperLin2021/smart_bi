from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class OrganizationCreate(BaseModel):
    name: str
    slug: str


class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None


class OrganizationOut(BaseModel):
    id: int
    name: str
    slug: str
    created_at: datetime

    class Config:
        from_attributes = True


class DepartmentCreate(BaseModel):
    name: str
    parent_id: Optional[int] = None
    sort_order: Optional[int] = None


class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[int] = None
    sort_order: Optional[int] = None


class DepartmentOut(BaseModel):
    id: int
    name: str
    org_id: int
    parent_id: Optional[int] = None
    sort_order: int = 0
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
