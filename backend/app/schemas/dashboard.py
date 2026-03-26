from pydantic import BaseModel
from typing import List


class MetricCard(BaseModel):
    label: str
    value: str
    trend: str


class ChartCard(BaseModel):
    title: str
    categories: List[str]
    values: List[float]


class AlertItem(BaseModel):
    line: str
    issue: str
    severity: str
    time: str


class DashboardSummary(BaseModel):
    metrics: List[MetricCard]
    charts: List[ChartCard]
    alerts: List[AlertItem]
