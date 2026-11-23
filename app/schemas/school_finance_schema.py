from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.finance_schema import AccountStatement, Amount, Money


class FinancePolicyIn(BaseModel):
    late_fee_enabled: bool = False
    grace_days: int = Field(default=5, ge=0, le=90)
    late_fee_kind: str = Field(default="percent", pattern=r"^(percent|fixed)$")
    late_fee_value: Money = Decimal("5")
    hold_enabled: bool = False
    hold_after_days: int = Field(default=30, ge=1, le=365)
    hold_min_amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    sibling_discount_enabled: bool = False
    sibling_second_percent: Decimal = Field(
        default=Decimal("10"), ge=0, le=100, max_digits=5, decimal_places=2
    )
    sibling_third_percent: Decimal = Field(
        default=Decimal("15"), ge=0, le=100, max_digits=5, decimal_places=2
    )
    auto_billing_enabled: bool = False
    billing_lead_days: int = Field(default=10, ge=0, le=60)
    reason: str = Field(min_length=3, max_length=250)


class FinancePolicyOut(BaseModel):
    late_fee_enabled: bool
    grace_days: int
    late_fee_kind: str
    late_fee_value: Amount
    hold_enabled: bool
    hold_after_days: int
    hold_min_amount: Amount
    sibling_discount_enabled: bool
    sibling_second_percent: float
    sibling_third_percent: float
    auto_billing_enabled: bool
    billing_lead_days: int


class AutomationRun(BaseModel):
    today: date
    simulated: bool
    billing_runs: list[dict]
    sibling_discounts: int
    late_fees: list[dict]
    holds_set: list[str]
    holds_lifted: list[str]


class FamilyMember(BaseModel):
    student_id: int
    student_name: str
    enrollment_number: str
    balance: Amount
    overdue_balance: Amount


class FamilyAccount(BaseModel):
    responsible: list[str]
    members: list[FamilyMember]
    balance: Amount
    overdue_balance: Amount
    statements: list[AccountStatement]


class AgingBuckets(BaseModel):
    current: Amount = Decimal("0")
    d1_30: Amount = Decimal("0")
    d31_60: Amount = Decimal("0")
    d61_90: Amount = Decimal("0")
    d90_plus: Amount = Decimal("0")
    total: Amount = Decimal("0")


class AgingGroup(AgingBuckets):
    label: str
    students: int = 0


class AgingSummary(BaseModel):
    as_of: date
    totals: AgingBuckets
    students_overdue: int
    groups: list[AgingGroup]


class AgingAccount(AgingBuckets):
    student_id: int
    student_name: str
    enrollment_number: str
    group: str
    family: str | None
    financial_hold: bool
    oldest_due: date | None


class IncomeRow(BaseModel):
    key: str
    label: str
    payments: int
    total: Amount


class IncomeReport(BaseModel):
    start: date
    end: date
    group_by: str
    total: Amount
    payments: int
    rows: list[IncomeRow]


class ExpectedMonth(BaseModel):
    month: str
    expected: Amount
    collected: Amount
    by_concept: dict[str, float]


class CashierDay(BaseModel):
    day: date
    payments: int
    total: Amount
    by_method: dict[str, float]
