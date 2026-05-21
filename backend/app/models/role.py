from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.db.base_class import Base


class Role(Base):
    __tablename__ = "roles"
    __table_args__ = (
        UniqueConstraint("code", "org_id", name="uq_roles_code_org"),
    )

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(64), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    is_builtin = Column(Boolean, default=False, nullable=False)
    data_scope = Column(String(32), nullable=True)
    menu_permissions = Column(Text, nullable=True)
    action_permissions = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    organization = relationship("Organization", backref="custom_roles")
