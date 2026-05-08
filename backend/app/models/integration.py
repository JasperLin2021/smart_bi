from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)

from app.db.base_class import Base


class IntegrationConfig(Base):
    __tablename__ = "integration_configs"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(32), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    enabled = Column(Boolean, default=False, nullable=False)
    corp_id = Column(String(128), nullable=True, index=True)
    agent_id = Column(String(128), nullable=True)
    app_secret = Column(String(512), nullable=True)
    callback_url = Column(String(512), nullable=True)
    robot_webhook_url = Column(String(512), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ExternalOrgBinding(Base):
    __tablename__ = "external_org_bindings"
    __table_args__ = (
        UniqueConstraint("provider", "external_corp_id", name="uq_external_org_provider_corp"),
    )

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(32), nullable=False, index=True)
    external_corp_id = Column(String(128), nullable=False, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ExternalIdentity(Base):
    __tablename__ = "external_identities"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "external_corp_id",
            "external_user_id",
            name="uq_external_identity",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(32), nullable=False, index=True)
    external_corp_id = Column(String(128), nullable=False, index=True)
    external_user_id = Column(String(128), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    display_name = Column(String(128), nullable=True)
    email = Column(String(256), nullable=True)
    mobile = Column(String(64), nullable=True)
    department_ids_json = Column(Text, nullable=True)
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ExternalPermissionMapping(Base):
    __tablename__ = "external_permission_mappings"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(32), nullable=False, index=True)
    external_corp_id = Column(String(128), nullable=False, index=True)
    external_department_id = Column(String(128), nullable=False, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    role = Column(String(32), default="user", nullable=False)
    data_scope = Column(String(32), nullable=True)
    menu_permissions = Column(Text, nullable=True)
    action_permissions = Column(Text, nullable=True)
    priority = Column(Integer, default=100, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class MessageDelivery(Base):
    __tablename__ = "message_deliveries"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(32), nullable=False, index=True)
    channel = Column(String(32), nullable=False, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    recipient_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    recipient_external_user_id = Column(String(128), nullable=True)
    org_id = Column(Integer, nullable=True, index=True)
    title = Column(String(256), nullable=False)
    content = Column(Text, nullable=False)
    link_url = Column(String(512), nullable=True)
    status = Column(String(32), default="pending", nullable=False, index=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    sent_at = Column(DateTime, nullable=True)
