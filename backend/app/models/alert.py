from sqlalchemy import Column, DateTime, Integer, String, Text, Boolean, func
from app.db.base_class import Base


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    dataset_id = Column(Integer, nullable=True, index=True)
    datasource_id = Column(Integer, nullable=True, index=True)
    metric_id = Column(Integer, nullable=True)
    metric_name = Column(String(128), nullable=True)

    # 时间范围
    time_range = Column(Integer, default=1)
    time_range_unit = Column(String(16), default="day")  # day / week / month

    # 维度条件 (JSON array)
    dimension_conditions = Column(Text, nullable=True)

    # 指标条件 (JSON array: [{metric, operator, value}])
    metric_conditions = Column(Text, nullable=True)

    # 检测通知周期
    check_period = Column(Integer, default=1)
    check_period_unit = Column(String(16), default="hour")  # minute / hour / day

    # 待办人 / 抄送人 (JSON arrays of user IDs)
    assignees = Column(Text, nullable=True)
    cc_users = Column(Text, nullable=True)

    # 订阅方式
    notify_system = Column(Boolean, default=True)
    notify_email = Column(Boolean, default=False)
    notify_wechat = Column(Boolean, default=False)
    notify_dingtalk = Column(Boolean, default=False)

    # 邮件收件人（逗号分隔）
    email_recipients = Column(Text, nullable=True)

    # 预警内容
    content = Column(Text, nullable=True)

    auto_create_action_item = Column(Boolean, default=False)
    action_item_assignee_id = Column(Integer, nullable=True)

    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
