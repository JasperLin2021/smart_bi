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
