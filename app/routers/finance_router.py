from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import ensure_student_access, get_current_user, require_roles
from app.db.Session import get_db
from app.models.finance_model import (
    Charge,
    FinancialAdjustment,
    Installment,
    Payment,
    PaymentPlan,
    StudentAccount,
)
from app.models.student_model import Student
from app.models.user_model import User
from app.schemas.finance_schema import (
    AccountUpdate,
    AdjustmentCreate,
    ChargeCreate,
    FinanceAccountListItem,
    FinanceTransaction,
    PaymentCreate,
    PaymentPlanCreate,
    StudentFinanceSummary,
)

router = APIRouter(prefix="/finance", tags=["finance"])


def get_or_create_account(db: Session, student_id: int) -> StudentAccount:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")
    account = db.query(StudentAccount).filter(StudentAccount.student_id == student_id).first()
    if account is None:
        account = StudentAccount(student_id=student_id)
        db.add(account)
        db.commit()
        db.refresh(account)
    return account


def build_summary(account: StudentAccount) -> StudentFinanceSummary:
    total_charges = round(sum(item.amount for item in account.charges), 2)
    total_payments = round(sum(item.amount for item in account.payments), 2)
    adjustment_total = round(
        sum(
            item.amount if item.kind in {"late_fee", "debit"} else -item.amount
            for item in account.adjustments
        ),
        2,
    )
    overdue = round(sum(item.amount for item in account.charges if item.due_date < date.today()), 2)
    credits = sum(
        item.amount
        for item in account.adjustments
        if item.kind in {"discount", "scholarship", "credit"}
    )
    applied_to_overdue = min(overdue, total_payments + credits)
    transactions = [
        FinanceTransaction(
            transaction_id=item.charge_id,
            type="charge",
            description=item.description,
            amount=item.amount,
            date=item.created_at,
            due_date=item.due_date,
        )
        for item in account.charges
    ] + [
        FinanceTransaction(
            transaction_id=item.payment_id,
            type="payment",
            description=item.reference if not item.note else f"{item.reference} · {item.note}",
            amount=item.amount,
            date=item.paid_at,
        )
        for item in account.payments
    ]
    transactions.sort(key=lambda item: item.date, reverse=True)
    return StudentFinanceSummary(
        student_id=account.student_id,
        enrollment_number=account.student.enrollment_number,
        student_name=f"{account.student.first_name} {account.student.last_name}",
        cutoff_day=account.cutoff_day,
        due_day=account.due_day,
        total_charges=total_charges,
        total_payments=total_payments,
        balance=round(total_charges + adjustment_total - total_payments, 2),
        total_adjustments=adjustment_total,
        overdue_balance=round(max(overdue - applied_to_overdue, 0), 2),
        transactions=transactions,
    )


@router.get(
    "/accounts",
    response_model=list[FinanceAccountListItem],
    dependencies=[Depends(require_roles("admin"))],
)
def list_accounts(db: Session = Depends(get_db)):
    results = []
    for student in db.query(Student).filter(Student.active.is_(True)).all():
        summary = build_summary(get_or_create_account(db, student.student_id))
        results.append(
            FinanceAccountListItem(
                student_id=student.student_id,
                enrollment_number=student.enrollment_number,
                student_name=f"{student.first_name} {student.last_name}",
                balance=summary.balance,
                overdue_balance=summary.overdue_balance,
            )
        )
    return results


@router.get("/students/{student_id}", response_model=StudentFinanceSummary)
def student_finance(
    student_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    ensure_student_access(user, student_id)
    return build_summary(get_or_create_account(db, student_id))


@router.put(
    "/students/{student_id}/account",
    response_model=StudentFinanceSummary,
    dependencies=[Depends(require_roles("admin"))],
)
def update_account(student_id: int, data: AccountUpdate, db: Session = Depends(get_db)):
    account = get_or_create_account(db, student_id)
    account.cutoff_day = data.cutoff_day
    account.due_day = data.due_day
    db.commit()
    db.refresh(account)
    return build_summary(account)


@router.post(
    "/students/{student_id}/charges",
    response_model=StudentFinanceSummary,
    dependencies=[Depends(require_roles("admin"))],
)
def add_charge(student_id: int, data: ChargeCreate, db: Session = Depends(get_db)):
    account = get_or_create_account(db, student_id)
    db.add(Charge(student_account_id=account.student_account_id, **data.model_dump()))
    db.commit()
    db.refresh(account)
    return build_summary(account)


@router.post(
    "/students/{student_id}/payments",
    response_model=StudentFinanceSummary,
    dependencies=[Depends(require_roles("admin"))],
)
def add_payment(student_id: int, data: PaymentCreate, db: Session = Depends(get_db)):
    account = get_or_create_account(db, student_id)
    current = build_summary(account)
    if data.amount > current.balance:
        raise HTTPException(status_code=422, detail="Payment cannot exceed the current balance")
    sequence = db.query(Payment).count() + 1
    db.add(
        Payment(
            student_account_id=account.student_account_id,
            paid_at=datetime.now(UTC).replace(tzinfo=None),
            receipt_number=f"REC-{date.today().year}-{sequence:06d}",
            **data.model_dump(),
        )
    )
    db.commit()
    db.refresh(account)
    return build_summary(account)


@router.post(
    "/students/{student_id}/adjustments",
    response_model=StudentFinanceSummary,
    dependencies=[Depends(require_roles("admin"))],
)
def add_adjustment(student_id: int, data: AdjustmentCreate, db: Session = Depends(get_db)):
    account = get_or_create_account(db, student_id)
    if data.kind in {"discount", "scholarship", "credit"}:
        current = build_summary(account)
        if data.amount > current.balance:
            raise HTTPException(status_code=422, detail="Credit cannot exceed the current balance")
    db.add(FinancialAdjustment(student_account_id=account.student_account_id, **data.model_dump()))
    db.commit()
    db.refresh(account)
    return build_summary(account)


@router.post(
    "/students/{student_id}/payment-plans",
    dependencies=[Depends(require_roles("admin"))],
)
def create_payment_plan(student_id: int, data: PaymentPlanCreate, db: Session = Depends(get_db)):
    account = get_or_create_account(db, student_id)
    balance = build_summary(account).balance
    if balance <= 0:
        raise HTTPException(status_code=409, detail="The account has no pending balance")
    plan = PaymentPlan(
        student_account_id=account.student_account_id,
        name=data.name,
        active=True,
    )
    db.add(plan)
    db.flush()
    base_amount = round(balance / data.installments, 2)
    remaining = balance
    for index in range(data.installments):
        amount = remaining if index == data.installments - 1 else base_amount
        remaining = round(remaining - amount, 2)
        db.add(
            Installment(
                payment_plan_id=plan.payment_plan_id,
                due_date=data.first_due_date + timedelta(days=30 * index),
                amount=amount,
                paid=False,
            )
        )
    db.commit()
    return {"payment_plan_id": plan.payment_plan_id, "installments": data.installments}
