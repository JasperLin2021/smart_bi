from sqlalchemy import Column, DateTime, Integer, String, Text, func

from app.db.base_class import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    actor_user_id = Column(Integer, nullable=True, index=True)
    actor_username = Column(String(128), nullable=True)
    actor_role = Column(String(32), nullable=True)
    org_id = Column(Integer, nullable=True, index=True)
    action = Column(String(128), nullable=False, index=True)
    resource_type = Column(String(64), nullable=False, index=True)
    resource_id = Column(String(128), nullable=True, index=True)
    resource_name = Column(String(256), nullable=True)
    status = Column(String(32), nullable=False, default="success", index=True)
    message = Column(Text, nullable=True)
    detail_json = Column(Text, nullable=True)
    ip_address = Column(String(64), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)
