from sqlalchemy import Column, DateTime, Integer, String, Boolean, Text, func
from app.db.base_class import Base


class QueryHistory(Base):
    __tablename__ = "query_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    datasource_id = Column(Integer, index=True, nullable=True)
    question = Column(String(512), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    favorite = Column(Boolean, default=False)
    # 保存完整对话数据
    sql_query = Column(Text, nullable=True)
    result_json = Column(Text, nullable=True)  # JSON 字符串
    summary = Column(Text, nullable=True)
    mode = Column(String(32), nullable=True)
