from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func

from app.db.base_class import Base


class CatalogCategory(Base):
    __tablename__ = "catalog_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    parent_id = Column(Integer, ForeignKey("catalog_categories.id", ondelete="SET NULL"), nullable=True, index=True)
    org_id = Column(Integer, nullable=True, index=True)
    sort_order = Column(Integer, nullable=False, server_default="0", default=0)
    created_at = Column(DateTime, server_default=func.now())


class DataAsset(Base):
    __tablename__ = "data_assets"

    id = Column(Integer, primary_key=True, index=True)
    asset_type = Column(String(32), nullable=False, index=True)
    asset_id = Column(Integer, nullable=True, index=True)
    name = Column(String(128), nullable=False, index=True)
    description = Column(Text, nullable=True)
    datasource_id = Column(Integer, nullable=True, index=True)
    org_id = Column(Integer, nullable=True, index=True)
    owner_id = Column(Integer, nullable=True, index=True)
    category_id = Column(Integer, ForeignKey("catalog_categories.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(32), default="draft", nullable=False, index=True)
    tags = Column(JSON, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    view_count = Column(Integer, default=0, nullable=False, server_default="0")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class AssetLineage(Base):
    __tablename__ = "asset_lineage"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("data_assets.id", ondelete="CASCADE"), nullable=False, index=True)
    target_id = Column(Integer, ForeignKey("data_assets.id", ondelete="CASCADE"), nullable=False, index=True)
    rel_type = Column(String(32), nullable=False, default="derives_from")
    org_id = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (UniqueConstraint("source_id", "target_id", name="uq_asset_lineage"),)


class AssetSubscription(Base):
    __tablename__ = "asset_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id = Column(Integer, ForeignKey("data_assets.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (UniqueConstraint("user_id", "asset_id", name="uq_asset_subscription"),)


class AssetNotification(Base):
    __tablename__ = "asset_notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id = Column(Integer, ForeignKey("data_assets.id", ondelete="CASCADE"), nullable=False, index=True)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False, server_default="0")
    created_at = Column(DateTime, server_default=func.now())
