from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


# ── CatalogCategory ──────────────────────────────────────────────────────────

class CatalogCategoryBase(BaseModel):
    name: str
    parent_id: Optional[int] = None
    org_id: Optional[int] = None


class CatalogCategoryCreate(CatalogCategoryBase):
    pass


class CatalogCategoryUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[int] = None


class CatalogCategoryOut(CatalogCategoryBase):
    id: int
    sort_order: int = 0
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CatalogCategoryTree(CatalogCategoryOut):
    children: list[CatalogCategoryTree] = []


class CategoryReorderItem(BaseModel):
    id: int
    sort_order: int


# ── DataAsset ─────────────────────────────────────────────────────────────────

class DataAssetBase(BaseModel):
    asset_type: str
    asset_id: Optional[int] = None
    name: str
    description: Optional[str] = None
    datasource_id: Optional[int] = None
    org_id: Optional[int] = None
    owner_id: Optional[int] = None
    category_id: Optional[int] = None
    status: str = "draft"
    tags: Optional[list[str]] = None
    metadata_json: Optional[dict[str, Any]] = None


class DataAssetCreate(DataAssetBase):
    pass


class DataAssetUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    datasource_id: Optional[int] = None
    category_id: Optional[int] = None
    status: Optional[str] = None
    tags: Optional[list[str]] = None
    metadata_json: Optional[dict[str, Any]] = None


class DataAssetStatusUpdate(BaseModel):
    status: str


class DataAssetCategoryUpdate(BaseModel):
    category_id: Optional[int] = None


class DataAssetOut(DataAssetBase):
    id: int
    view_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DataAssetListResponse(BaseModel):
    items: list[DataAssetOut]


# ── Fields ────────────────────────────────────────────────────────────────────

class FieldInfo(BaseModel):
    name: str
    type: str = "unknown"
    description: Optional[str] = None


class AssetFieldsResponse(BaseModel):
    columns: list[FieldInfo]


# ── Preview ───────────────────────────────────────────────────────────────────

class AssetPreviewResponse(BaseModel):
    columns: list[str]
    rows: list[dict[str, Any]]


# ── References ────────────────────────────────────────────────────────────────

class AssetReferenceItem(BaseModel):
    type: str
    name: str
    id: int


class AssetReferencesResponse(BaseModel):
    count: int
    references: list[AssetReferenceItem]


# ── Lineage ───────────────────────────────────────────────────────────────────

class LineageNode(BaseModel):
    id: int
    name: str
    asset_type: str


class LineageEdge(BaseModel):
    source: int
    target: int
    rel_type: str


class AssetLineageResponse(BaseModel):
    nodes: list[LineageNode]
    edges: list[LineageEdge]


class LineageCreate(BaseModel):
    source_id: int
    target_id: int
    rel_type: str = "derives_from"
    org_id: Optional[int] = None


class LineageOut(BaseModel):
    id: int
    source_id: int
    target_id: int
    rel_type: str
    org_id: Optional[int] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Subscription & Notification ───────────────────────────────────────────────

class AssetSubscriptionOut(BaseModel):
    id: int
    user_id: int
    asset_id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SubscriptionStatus(BaseModel):
    subscribed: bool


class AssetNotificationOut(BaseModel):
    id: int
    user_id: int
    asset_id: int
    message: str
    is_read: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    items: list[AssetNotificationOut]
    unread_count: int
