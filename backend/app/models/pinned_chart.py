from sqlalchemy import Column, DateTime, Integer, String, Text, func
from app.db.base_class import Base


class PinnedChart(Base):
    """固定到Dashboard的图表"""
    __tablename__ = "pinned_charts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    datasource_id = Column(Integer, index=True, nullable=True)
    title = Column(String(128), nullable=False)
    description = Column(String(256), nullable=True)
    sql_query = Column(Text, nullable=False)
    chart_type = Column(String(32), default="bar")  # line, bar, area, pie, donut, scatter, combo, kpi, table
    sort_order = Column(String(16), default="desc")  # none, asc, desc
    display_order = Column(Integer, default=0)  # 显示顺序
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
