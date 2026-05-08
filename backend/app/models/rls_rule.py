from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from app.db.base_class import Base


class RLSRule(Base):
    __tablename__ = "rls_rules"

    id = Column(Integer, primary_key=True, index=True)
    datasource_id = Column(Integer, ForeignKey("datasources.id", ondelete="CASCADE"), nullable=False, index=True)
    # 作用范围：org_id 不为空 → 整个组织生效；user_id 不为空 → 特定用户生效
    org_id = Column(Integer, nullable=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    table_name = Column(String(128), nullable=False)
    column_name = Column(String(128), nullable=False)
    # operator: = | != | > | < | >= | <= | IN | NOT IN | LIKE
    operator = Column(String(16), nullable=False, default="=")
    filter_value = Column(String(512), nullable=False)
    is_active = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
