from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field, StringConstraints


def validate_money(value: Decimal) -> Decimal:
    if not value.is_finite() or value <= 0 or value > Decimal("999999999.99"):
        raise ValueError("El monto debe ser positivo, finito y menor a RD$1,000,000,000")
    if value != value.quantize(Decimal("0.01")):
        raise ValueError("El monto admite como máximo dos decimales")
    return value


Money = Annotated[Decimal, AfterValidator(validate_money)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=250)]
Reference = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]


class AccountUpdate(BaseModel):
    cutoff_day: int = Field(ge=1, le=31)
    due_day: int = Field(ge=1, le=31)


class ChargeCreate(BaseModel):
    description: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)
    ]
    amount: Money
    due_date: date | None = None


class PaymentCreate(BaseModel):
    amount: Money
    reference: Reference
    note: str = Field(default="", max_length=250)
    method: str = Field(default="cash", pattern=r"^cash$")
    idempotency_key: Reference | None = None


class AdjustmentCreate(BaseModel):
    kind: str = Field(pattern=r"^(discount|scholarship|late_fee|credit|debit)$")
    description: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)
    ]
    amount: Money
    due_date: date | None = None


class PaymentPlanCreate(BaseModel):
    name: Reference
    installments: int = Field(ge=2, le=24)
    first_due_date: date


class FinanceTransaction(BaseModel):
    transaction_id: int
    type: str
    description: str
    amount: float
    date: datetime
    due_date: date | None = None
    direction: str = "debit"
    status: str = "posted"
    kind: str | None = None
    method: str | None = None
    receipt_number: str | None = None
    created_by: int | None = None
    reversal_reason: str | None = None


class StudentFinanceSummary(BaseModel):
    currency: str = "DOP"
    student_id: int
    enrollment_number: str
    student_name: str
    cutoff_day: int
    due_day: int
    total_charges: float
    total_payments: float
    total_adjustments: float = 0
    balance: float
    overdue_balance: float
    transactions: list[FinanceTransaction]


class FinanceAccountListItem(BaseModel):
    student_id: int
    enrollment_number: str
    student_name: str
    balance: float
    overdue_balance: float


class BillingConceptCreate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
    description: str = Field(default="", max_length=250)
    amount: Money
    frequency: str = Field(default="once", pattern=r"^(once|monthly|term|annual)$")
    active: bool = True


class ReasonRequest(BaseModel):
    reason: Reason


class TransferCreate(BaseModel):
    amount: Money
    reference: Reference
    bank: Reference
    note: str = Field(default="", max_length=250)
    proof_base64: str = Field(min_length=1, max_length=2800000)


class TransferReview(ReasonRequest):
    approve: bool


class SimulationCreate(BaseModel):
    amount: Money
    outcome: str = Field(pattern=r"^(approved|declined|cancelled)$")


Cycle = Annotated[str, StringConstraints(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]
PlanName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
ChargeText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=150)]


class BillingPlanTargets(BaseModel):
    """Careers (or school grades), extra students and excluded students."""

    career_ids: list[int] = Field(default_factory=list, max_length=500)
    student_ids: list[int] = Field(default_factory=list, max_length=5000)
    excluded_student_ids: list[int] = Field(default_factory=list, max_length=5000)


class BillingPlanCreate(BaseModel):
    name: PlanName
    charge_description: ChargeText
    billing_concept_id: int | None = None
    amount: Money
    frequency: str = Field(default="monthly", pattern=r"^(monthly|single)$")
    start_month: Cycle
    end_month: Cycle | None = None
    due_day: int = Field(default=5, ge=1, le=28)
    period_id: int | None = None
    targets: BillingPlanTargets = Field(default_factory=BillingPlanTargets)


class BillingPlanUpdate(BaseModel):
    name: PlanName | None = None
    charge_description: ChargeText | None = None
    amount: Money | None = None
    end_month: Cycle | None = None
    due_day: int | None = Field(default=None, ge=1, le=28)
    active: bool | None = None


class BillingPlanOut(BaseModel):
    billing_plan_id: int
    name: str
    charge_description: str
    billing_concept_id: int | None
    amount: Decimal
    frequency: str
    start_month: str
    end_month: str
    due_day: int
    period_id: int | None
    active: bool
    targets: BillingPlanTargets
    cycles: list[str]
    generated_cycles: list[str]
    next_cycle: str | None


class BillingCycleRequest(BaseModel):
    cycle: Cycle


class BillingRunCreate(BillingCycleRequest):
    reason: Reason = "Generación de cargos del ciclo"
    idempotency_key: Reference | None = None


class BillingPreviewStudent(BaseModel):
    student_id: int
    enrollment_number: str
    student_name: str
    has_payment_plan: bool = False


class BillingPreview(BaseModel):
    cycle: str
    cycle_label: str
    due_date: date
    amount: Decimal
    charge_description: str
    to_charge: int
    already_charged: int
    total: Decimal
    with_payment_plan: int
    students: list[BillingPreviewStudent]


class BillingRunOut(BaseModel):
    billing_run_id: int
    billing_plan_id: int
    cycle: str
    charge_count: int
    total: Decimal
    reason: str
    created_by: int
    created_at: datetime
