from datetime import date, datetime

from pydantic import BaseModel, Field


class AccountUpdate(BaseModel):
    cutoff_day: int = Field(ge=1, le=31)
    due_day: int = Field(ge=1, le=31)


class ChargeCreate(BaseModel):
    description: str = Field(min_length=2, max_length=200)
    amount: float = Field(gt=0)
    due_date: date


class PaymentCreate(BaseModel):
    amount: float = Field(gt=0)
    reference: str = Field(min_length=2, max_length=100)
    note: str = Field(default="", max_length=250)


class AdjustmentCreate(BaseModel):
    kind: str = Field(pattern=r"^(discount|scholarship|late_fee|credit|debit)$")
    description: str = Field(min_length=2, max_length=200)
    amount: float = Field(gt=0)


class PaymentPlanCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    installments: int = Field(ge=2, le=24)
    first_due_date: date


class FinanceTransaction(BaseModel):
    transaction_id: int
    type: str
    description: str
    amount: float
    date: datetime
    due_date: date | None = None


class StudentFinanceSummary(BaseModel):
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
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=250)
    amount: float = Field(gt=0)
    frequency: str = Field(default="once", pattern=r"^(once|monthly|term|annual)$")
    active: bool = True
