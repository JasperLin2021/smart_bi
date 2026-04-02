from sqlalchemy import Column, DateTime, Integer, String, Text, func

from app.db.base_class import Base


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    route = Column(String(128), nullable=False)
    prompt = Column(Text, nullable=False)
    plan_json = Column(Text, nullable=True)
    execution_json = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="planned")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
