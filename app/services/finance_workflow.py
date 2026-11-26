"""Internal DOP ledger. Never contacts a bank or stores card data."""

import base64
import binascii
import calendar
import json
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException

from app.models.finance_model import FinanceEvent, Payment, StudentAccount
from app.models.student_model import Student
from app.schemas.finance_schema import FinanceTransaction, StudentFinanceSummary
from app.services.business_time import business_date as business_date
from app.services.write_locks import lock_scope

CREDIT_KINDS = {"discount", "scholarship", "credit"}


def now():
    return datetime.now(UTC).replace(tzinfo=None)


def cents(value):
    return int((Decimal(str(value)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def money(value):
    """Integer cents to an exact Decimal amount."""
    return (Decimal(int(value)) / 100).quantize(Decimal("0.01"))


def active(item):
    return item.status == "posted"


def credits(account):
    return sum(cents(p.amount) for p in account.payments if active(p)) + sum(
        cents(a.amount) for a in account.adjustments if active(a) and a.kind in CREDIT_KINDS
    )


def empty_account(student):
    """Unsaved account with default terms; reads never persist accounts."""
    return StudentAccount(
        student_id=student.student_id,
        student=student,
        cutoff_day=15,
        due_day=30,
        ledger_version=0,
        charges=[],
        payments=[],
        adjustments=[],
    )


def get_account(db, student_id, write=False):
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(404, "Estudiante no encontrado")
    account = db.query(StudentAccount).filter_by(student_id=student_id).first()
    if account is None:
        account = empty_account(student)
        if write:
            db.add(account)
            db.flush()
    return account


def lock_finance(db):
    # Serializes posting, approval, reversal and closing (see write_locks.py).
    lock_scope(db, "finance")


def writable_account(db, student_id):
    lock_finance(db)
    account = get_account(db, student_id, write=True)
    account.ledger_version += 1
    return account


def event(db, user, student_id, action, detail):
    db.add(
        FinanceEvent(
            user_id=user.user_id if user is not None else None,
            student_id=student_id,
            action=action,
            detail=json.dumps(detail, ensure_ascii=False, default=str),
        )
    )


def first_unpaid(account_obligations, available, today):
    """First obligation still unpaid on or after ``today`` (credits apply oldest first)."""
    for due, _, _, _, amount in sorted(account_obligations):
        applied = min(available, amount)
        available -= applied
        if amount - applied > 0 and due >= today:
            return due, amount - applied
    return None, None


def obligations_of(account):
    items = [
        (c.due_date, c.created_at, "charge", c.charge_id, cents(c.amount))
        for c in account.charges
        if active(c)
    ]
    items += [
        (
            a.due_date or business_date(a.created_at),
            a.created_at,
            "adjustment",
            a.adjustment_id,
            cents(a.amount),
        )
        for a in account.adjustments
        if active(a) and a.kind not in CREDIT_KINDS
    ]
    return items


def upcoming_due(account):
    """(date, amount) of the next installment to pay, or (None, None)."""
    due, remaining = first_unpaid(obligations_of(account), credits(account), business_date())
    return due, (money(remaining) if remaining is not None else None)


def summary(account):
    charges = sum(cents(c.amount) for c in account.charges if active(c))
    payments = sum(cents(p.amount) for p in account.payments if active(p))
    adjustments = sum(
        cents(a.amount) * (-1 if a.kind in CREDIT_KINDS else 1)
        for a in account.adjustments
        if active(a)
    )
    obligations = obligations_of(account)
    available = credits(account)
    overdue = 0
    for due, _, _, _, amount in sorted(obligations):
        applied = min(available, amount)
        available -= applied
        if due < business_date():
            overdue += amount - applied
    transactions = (
        [
            FinanceTransaction(
                transaction_id=c.charge_id,
                type="charge",
                description=c.description,
                amount=c.amount,
                date=c.created_at,
                due_date=c.due_date,
                direction="debit",
                status=c.status,
                created_by=c.created_by,
                reversal_reason=c.reversal_reason,
            )
            for c in account.charges
        ]
        + [
            FinanceTransaction(
                transaction_id=p.payment_id,
                type="payment",
                description=p.reference + (" · " + p.note if p.note else ""),
                amount=p.amount,
                date=p.paid_at,
                direction="credit",
                status=p.status,
                method=p.method,
                receipt_number=p.receipt_number,
                created_by=p.created_by,
                reversal_reason=p.reversal_reason,
            )
            for p in account.payments
        ]
        + [
            FinanceTransaction(
                transaction_id=a.adjustment_id,
                type="adjustment",
                description=a.description,
                amount=a.amount,
                date=a.created_at,
                due_date=a.due_date,
                direction="credit" if a.kind in CREDIT_KINDS else "debit",
                kind=a.kind,
                status=a.status,
                created_by=a.created_by,
                reversal_reason=a.reversal_reason,
            )
            for a in account.adjustments
        ]
    )
    transactions.sort(key=lambda t: (t.date, t.type, t.transaction_id), reverse=True)
    return StudentFinanceSummary(
        student_id=account.student_id,
        enrollment_number=account.student.enrollment_number,
        student_name=account.student.full_name,
        cutoff_day=account.cutoff_day,
        due_day=account.due_day,
        total_charges=money(charges),
        total_payments=money(payments),
        total_adjustments=money(adjustments),
        balance=money(charges + adjustments - payments),
        overdue_balance=money(overdue),
        transactions=transactions,
    )


def add_months(day, months):
    index = day.year * 12 + day.month - 1 + months
    year, month = divmod(index, 12)
    month += 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def next_due(account):
    today = business_date()
    result = today.replace(
        day=min(account.due_day, calendar.monthrange(today.year, today.month)[1])
    )
    if result < today:
        first = add_months(today.replace(day=1), 1)
        result = first.replace(
            day=min(account.due_day, calendar.monthrange(first.year, first.month)[1])
        )
    return result


def check_open_day(db, day=None):
    from app.models.finance_model import CashClosing

    if db.query(CashClosing).filter_by(closing_date=day or business_date()).first():
        raise HTTPException(
            409, "La caja de ese día está cerrada. No se permiten pagos ni reversos."
        )


def post_payment(db, account, data, user, method="cash", key=None, online=False):
    """Post a payment. ``online``: the gateway already charged the card (Fase 4 E),
    so it is recorded even after the day's cash closing or above the balance."""
    if not online:
        check_open_day(db)
    amount = cents(data.amount)
    if amount > cents(summary(account).balance) and not online:
        raise HTTPException(422, "El pago no puede superar el balance pendiente")
    if db.query(Payment).filter_by(reference=data.reference).first():
        raise HTTPException(409, "La referencia ya fue registrada; verifica el pago existente")
    payment = Payment(
        student_account_id=account.student_account_id,
        amount=money(amount),
        reference=data.reference,
        note=data.note,
        paid_at=now(),
        method=method,
        status="posted",
        created_by=user.user_id,
        idempotency_key=key,
    )
    db.add(payment)
    db.flush()
    payment.receipt_number = f"REC-{business_date().year}-{payment.payment_id:08d}"
    event(
        db,
        user,
        account.student_id,
        "payment.posted",
        {
            "payment_id": payment.payment_id,
            "amount_cents": amount,
            "reference": payment.reference,
            "method": method,
            "receipt": payment.receipt_number,
        },
    )
    # A payment can bring the account up to date: lift an automatic hold (Fase 3 E).
    from app.services.finance_automation import refresh_auto_hold

    db.flush()
    db.expire(account, ["payments"])
    refresh_auto_hold(db, account, user)
    # Fiscal receipt (Fase 4 F): issued now or left pending; never blocks the payment.
    from app.services.fiscal.issuing import after_payment

    after_payment(db, payment, account, user)
    return payment


def plan_summary(account, plan):
    extra = (
        cents(plan.credit_snapshot)
        if not plan.active and plan.credit_snapshot is not None
        else max(credits(account) - cents(plan.credit_baseline), 0)
    )
    items = []
    for item in sorted(plan.installments, key=lambda i: (i.due_date, i.installment_id)):
        # Old paid flags remain authoritative for old plans; new plans derive all states.
        initial = cents(item.amount) if not plan.created_at and item.paid else 0
        allocated = min(cents(item.amount) - initial, extra)
        extra -= allocated
        paid = initial + allocated
        remaining = cents(item.amount) - paid
        items.append(
            {
                "installment_id": item.installment_id,
                "due_date": item.due_date,
                "amount": item.amount,
                "paid_amount": money(paid),
                "remaining": money(remaining),
                "status": "paid"
                if not remaining
                else "overdue"
                if item.due_date < business_date()
                else "partial"
                if paid
                else "pending",
            }
        )
    return {
        "payment_plan_id": plan.payment_plan_id,
        "name": plan.name,
        "active": plan.active,
        "created_at": plan.created_at,
        "installments": items,
    }


def decode_proof(proof_base64: str) -> tuple[bytes, str]:
    """Bank transfer proof: PDF, PNG or JPEG of at most 2 MB."""
    try:
        proof = base64.b64decode(proof_base64, validate=True)
    except (ValueError, binascii.Error):
        raise HTTPException(422, "Comprobante inválido") from None
    mime = (
        "application/pdf"
        if proof.startswith(b"%PDF-")
        else "image/png"
        if proof.startswith(b"\x89PNG\r\n\x1a\n")
        else "image/jpeg"
        if proof.startswith(b"\xff\xd8\xff")
        else None
    )
    if not mime or len(proof) > 2 * 1024 * 1024:
        raise HTTPException(422, "Usa PDF, PNG o JPEG de máximo 2 MB")
    return proof, mime


def ensure_new_reference(db, reference: str) -> None:
    """A bank reference is reported once: single transfer, family batch or payment."""
    from app.models.finance_model import TransferBatch, TransferRequest

    if (
        db.query(TransferRequest).filter_by(reference=reference).first()
        or db.query(TransferBatch).filter_by(reference=reference).first()
        or db.query(Payment).filter_by(reference=reference).first()
    ):
        raise HTTPException(409, "Referencia ya registrada")
