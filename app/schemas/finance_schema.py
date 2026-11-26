from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    Field,
    PlainSerializer,
    StringConstraints,
    field_validator,
)


def validate_money(value: Decimal) -> Decimal:
    if not value.is_finite() or value <= 0 or value > Decimal("999999999.99"):
        raise ValueError("El monto debe ser positivo, finito y menor a RD$1,000,000,000")
    if value != value.quantize(Decimal("0.01")):
        raise ValueError("El monto admite como máximo dos decimales")
    return value


Money = Annotated[Decimal, AfterValidator(validate_money)]
# Output amounts: exact Decimal in Python, a JSON number for the interface.
Amount = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=250)]
Reference = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]


class AccountUpdate(BaseModel):
    cutoff_day: int = Field(ge=1, le=31)
    due_day: int = Field(ge=1, le=31)


def check_rate(value):
    """ITBIS rates of the Dominican Republic (Fase 4 F)."""
    if Decimal(value) not in (Decimal("0"), Decimal("16"), Decimal("18")):
        raise ValueError("El ITBIS debe ser 0 (exento), 16 o 18")
    return Decimal(value)


class ChargeCreate(BaseModel):
    description: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)
    ]
    amount: Money
    due_date: date | None = None
    # ITBIS included in the amount (Fase 4 F): 0 exempt (education), 16 or 18.
    itbis_rate: Decimal = Field(default=Decimal("0"))

    @field_validator("itbis_rate")
    @classmethod
    def known_rate(cls, value):
        return check_rate(value)


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
    itbis_rate: Decimal = Field(default=Decimal("0"))

    @field_validator("itbis_rate")
    @classmethod
    def known_rate(cls, value):
        return check_rate(value)


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


class GradeTarget(BaseModel):
    """A school grade: the members of that program's groups in the plan's year."""

    career_id: int
    grade_number: int = Field(ge=1, le=20)


class BillingPlanTargets(BaseModel):
    """Careers, school grades, extra students and excluded students."""

    career_ids: list[int] = Field(default_factory=list, max_length=500)
    grades: list[GradeTarget] = Field(default_factory=list, max_length=100)
    student_ids: list[int] = Field(default_factory=list, max_length=5000)
    excluded_student_ids: list[int] = Field(default_factory=list, max_length=5000)


class BillingPlanCreate(BaseModel):
    name: PlanName
    charge_description: ChargeText
    billing_concept_id: int | None = None
    amount: Money
    frequency: str = Field(default="monthly", pattern=r"^(monthly|single)$")
    # Without months, a plan with a school year bills every month of that year.
    start_month: Cycle | None = None
    end_month: Cycle | None = None
    due_day: int = Field(default=5, ge=1, le=28)
    period_id: int | None = None
    school_year_id: int | None = None
    sibling_discount: bool = False
    targets: BillingPlanTargets = Field(default_factory=BillingPlanTargets)


class BillingPlanUpdate(BaseModel):
    name: PlanName | None = None
    charge_description: ChargeText | None = None
    amount: Money | None = None
    end_month: Cycle | None = None
    due_day: int | None = Field(default=None, ge=1, le=28)
    active: bool | None = None
    sibling_discount: bool | None = None


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
    school_year_id: int | None = None
    sibling_discount: bool = False
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


class StatementObligation(BaseModel):
    """A charge or debit adjustment and how much of it is already covered."""

    type: str  # charge | adjustment
    obligation_id: int
    concept: str
    description: str
    due_date: date
    amount: Amount
    paid_amount: Amount
    remaining: Amount
    status: str  # paid | partial | pending | overdue


class StatementConcept(BaseModel):
    concept: str
    amount: Amount
    paid_amount: Amount
    remaining: Amount


class StatementPayment(BaseModel):
    payment_id: int
    amount: Amount
    reference: str
    method: str
    paid_at: datetime
    receipt_number: str | None
    # Fiscal receipt of the payment, if any (Fase 4 F).
    fiscal_document_id: int | None = None
    ncf: str | None = None


class PlanInstallment(BaseModel):
    installment_id: int
    due_date: date
    amount: Amount
    paid_amount: Amount
    remaining: Amount
    status: str


class PaymentPlanStatus(BaseModel):
    payment_plan_id: int
    name: str
    active: bool
    created_at: datetime | None
    installments: list[PlanInstallment]


class AccountStatement(BaseModel):
    student_id: int
    student_name: str
    enrollment_number: str
    balance: Amount
    overdue_balance: Amount
    next_due_date: date | None
    next_due_amount: Amount | None
    obligations: list[StatementObligation]
    concepts: list[StatementConcept]
    payments: list[StatementPayment]
    payment_plans: list[PaymentPlanStatus]


class TransferOut(BaseModel):
    transfer_request_id: int
    student_id: int
    reference: str
    bank: str
    note: str
    status: str
    submitted_at: datetime
    reviewed_at: datetime | None
    review_reason: str | None
    payment_id: int | None
    amount: Amount
    batch_id: int | None = None
    batch_reference: str | None = None
    batch_total: Amount | None = None
    batch_size: int | None = None


class TransferInboxItem(TransferOut):
    student_name: str
    enrollment_number: str


class FinanceOptions(BaseModel):
    currency: str
    gateway_enabled: bool
    transfer_instructions: str
    simulator_enabled: bool


class FinanceEventOut(BaseModel):
    id: int
    action: str
    detail: str
    created_at: datetime
    actor: str


class BillingConceptOut(BaseModel):
    billing_concept_id: int
    name: str
    description: str = ""
    amount: Amount
    frequency: str
    active: bool
    itbis_rate: Decimal = Decimal("0")
    model_config = {"from_attributes": True}


class CashClosingOut(BaseModel):
    cash_closing_id: int
    closing_date: date
    total_payments: Amount
    payment_count: int
    cash_total: Amount
    transfer_total: Amount
    closed_by: int
    created_at: datetime
    model_config = {"from_attributes": True}
