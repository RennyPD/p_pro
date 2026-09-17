from pydantic import BaseModel


class DashboardMetric(BaseModel):
    key: str
    label: str
    value: float | int
    note: str


class DashboardSummary(BaseModel):
    role: str
    metrics: list[DashboardMetric]
    active_period: str | None
    alerts: list[str]
