from sqlalchemy import Column, DateTime, Integer, String, Text, func
from app.db.base_class import Base


class AccessRequest(Base):
    __tablename__ = "access_requests"

    id = Column(Integer, primary_key=True, index=True)
    requester_id = Column(Integer, nullable=False, index=True)
    resource_type = Column(String(32), nullable=False, index=True)  # dataset | datasource
    resource_id = Column(Integer, nullable=False, index=True)
    resource_name = Column(String(128), nullable=True)
    reason = Column(Text, nullable=True)
    status = Column(String(16), default="pending", nullable=False, index=True)  # pending | approved | rejected
    reviewer_id = Column(Integer, nullable=True)
    review_comment = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    org_id = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
