from pydantic import BaseModel


class DashboardMetric(BaseModel):
    key: str
    label: str
    value: float | int | None
    note: str
    # How the interface shows it: default | danger | warning | success | info.
    tone: str = "default"
    # Where to act on it, when there is something to do.
    link: str | None = None
    # "money" values are shown as currency.
    format: str = "number"


class DashboardSummary(BaseModel):
    role: str
    display_name: str = ""
    metrics: list[DashboardMetric]
    active_period: str | None
    alerts: list[str]
