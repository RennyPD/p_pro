"""Sequences and issuing of fiscal receipts (Fase 4, block F1-F2).

- Numbers come from the institution's active range of each type, valid on
  the day, in order; each number is used once (the finance lock serializes).
- A posted payment gets its receipt (when the institution issues on payment).
  Without an available range the payment is still posted and the receipt is
  left pending, to issue later: a cashier is never blocked by fiscal setup.
- Lines are the charges the payment settles (oldest first), with the ITBIS
  included in each charge; what exceeds the charges is a payment on account.
"""

from datetime import UTC, date, datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.finance_model import Payment, StudentAccount
from app.models.fiscal_model import (
    FiscalDocument,
    FiscalDocumentLine,
    FiscalProfile,
    FiscalSequence,
)
from app.services.business_time import business_date
from app.services.finance_workflow import CREDIT_KINDS, active, cents, event, money
from app.services.fiscal.rules import (
    credit_note_type,
    max_number,
    number_text,
    receipt_type,
    split_itbis,
)

ALERT_REMAINING = 0.10
ALERT_DAYS = 30


class FiscalError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(409, detail)


def now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def profile_of(db: Session) -> FiscalProfile | None:
    return db.query(FiscalProfile).first()


def next_number(
    db: Session, doc_type: str, today: date | None = None
) -> tuple[str, FiscalSequence]:
    """Take the next number of ``doc_type``; the caller holds the finance lock."""
    today = today or business_date()
    candidates = (
        db.query(FiscalSequence)
        .filter(
            FiscalSequence.doc_type == doc_type,
            FiscalSequence.active.is_(True),
            FiscalSequence.next_number <= FiscalSequence.range_end,
        )
        .order_by(FiscalSequence.range_start)
        .with_for_update()
        .all()
    )
    for sequence in candidates:
        if sequence.expires_on is not None and sequence.expires_on < today:
            continue
        number = sequence.next_number
        sequence.next_number = number + 1
        return number_text(doc_type, number), sequence
    raise FiscalError(
        f"No hay secuencia {doc_type} vigente con números disponibles. Registra una nueva "
        "secuencia autorizada por la DGII"
    )


def sequence_alerts(db: Session, today: date | None = None) -> list[dict]:
    today = today or business_date()
    alerts = []
    for sequence in db.query(FiscalSequence).filter(FiscalSequence.active.is_(True)):
        size = sequence.range_end - sequence.range_start + 1
        left = max(0, sequence.range_end - sequence.next_number + 1)
        if sequence.expires_on is not None and sequence.expires_on < today:
            kind, text = "expired", f"La secuencia {sequence.doc_type} venció"
        elif left == 0:
            kind, text = "exhausted", f"La secuencia {sequence.doc_type} se agotó"
        elif left <= size * ALERT_REMAINING:
            kind, text = "low", f"Quedan {left} números {sequence.doc_type}"
        elif sequence.expires_on is not None and (sequence.expires_on - today).days <= ALERT_DAYS:
            kind = "expiring"
            text = f"La secuencia {sequence.doc_type} vence el {sequence.expires_on:%d/%m/%Y}"
        else:
            continue
        alerts.append(
            {"fiscal_sequence_id": sequence.fiscal_sequence_id, "kind": kind, "message": text}
        )
    return alerts


def lines_for_payment(db: Session, account: StudentAccount, payment: Payment) -> list[dict]:
    """The charges this payment settles, oldest first, after earlier credits."""
    charges = sorted(
        (c for c in account.charges if active(c)), key=lambda c: (c.due_date, c.charge_id)
    )
    earlier = sum(
        cents(p.amount)
        for p in account.payments
        if active(p) and (p.paid_at, p.payment_id) < (payment.paid_at, payment.payment_id)
    )
    earlier += sum(
        cents(a.amount) for a in account.adjustments if active(a) and a.kind in CREDIT_KINDS
    )
    remaining = cents(payment.amount)
    lines = []
    for charge in charges:
        amount = cents(charge.amount)
        covered = min(amount, earlier)
        earlier -= covered
        open_part = amount - covered
        if open_part <= 0 or remaining <= 0:
            continue
        take = min(open_part, remaining)
        remaining -= take
        lines.append({"description": charge.description, "rate": charge.itbis_rate, "cents": take})
    if remaining > 0:
        lines.append({"description": "Abono a cuenta", "rate": 0, "cents": remaining})
    return lines


def issue(
    db: Session,
    *,
    doc_type: str,
    lines: list[dict],
    buyer_name: str,
    buyer_tax_id: str,
    payment: Payment | None,
    student_id: int | None,
    user,
    affected: FiscalDocument | None = None,
) -> FiscalDocument:
    ncf, sequence = next_number(db, doc_type)
    document = FiscalDocument(
        doc_type=doc_type,
        ncf=ncf,
        fiscal_sequence_id=sequence.fiscal_sequence_id,
        sequence_expires_on=sequence.expires_on,
        status="issued",
        issued_at=now(),
        student_id=student_id,
        payment_id=payment.payment_id if payment else None,
        affected_document_id=affected.fiscal_document_id if affected else None,
        buyer_name=buyer_name,
        buyer_tax_id=buyer_tax_id,
        payment_method=payment.method if payment else "",
        subtotal=money(0),
        itbis=money(0),
        total=money(0),
        created_by=user.user_id if user else None,
    )
    subtotal = itbis = 0
    for line in lines:
        base, tax = split_itbis(line["cents"], line["rate"])
        subtotal, itbis = subtotal + base, itbis + tax
        document.lines.append(
            FiscalDocumentLine(
                description=line["description"][:200],
                itbis_rate=line["rate"],
                base_amount=money(base),
                itbis_amount=money(tax),
                line_total=money(line["cents"]),
            )
        )
    document.subtotal, document.itbis, document.total = (
        money(subtotal),
        money(itbis),
        money(subtotal + itbis),
    )
    db.add(document)
    db.flush()
    if student_id is not None:
        event(
            db,
            user,
            student_id,
            "fiscal.issued",
            {"ncf": ncf, "type": doc_type, "total_cents": subtotal + itbis},
        )
    return document


def issue_for_payment(db: Session, payment: Payment, account: StudentAccount, user):
    profile = profile_of(db)
    if profile is None or not profile.enabled:
        raise FiscalError("La institución no emite comprobantes fiscales")
    existing = (
        db.query(FiscalDocument)
        .filter(
            FiscalDocument.payment_id == payment.payment_id,
            FiscalDocument.affected_document_id.is_(None),
        )
        .first()
    )
    if existing is not None:
        return existing
    return issue(
        db,
        doc_type=receipt_type(profile.mode, account.bill_to_tax_id),
        lines=lines_for_payment(db, account, payment),
        buyer_name=account.bill_to_name or account.student.full_name,
        buyer_tax_id=account.bill_to_tax_id,
        payment=payment,
        student_id=account.student_id,
        user=user,
    )


def after_payment(db: Session, payment: Payment, account: StudentAccount, user) -> None:
    """Hook of post_payment: issue now, or leave the receipt pending (never block)."""
    profile = profile_of(db)
    if profile is None or not profile.enabled or profile.issue_on != "payment":
        return
    try:
        with db.begin_nested():
            issue_for_payment(db, payment, account, user)
    except FiscalError as problem:
        event(
            db,
            user,
            account.student_id,
            "fiscal.pending",
            {"payment_id": payment.payment_id, "reason": problem.detail},
        )


def credit_note(db: Session, document: FiscalDocument, user, reason: str) -> FiscalDocument:
    """A reversed payment: the credit note modifies the original receipt."""
    lines = [
        {"description": line.description, "rate": line.itbis_rate, "cents": cents(line.line_total)}
        for line in document.lines
    ]
    return issue(
        db,
        doc_type=credit_note_type(document.doc_type),
        lines=lines,
        buyer_name=document.buyer_name,
        buyer_tax_id=document.buyer_tax_id,
        payment=db.get(Payment, document.payment_id) if document.payment_id else None,
        student_id=document.student_id,
        user=user,
        affected=document,
    )


def validate_range(doc_type: str, start: int, end: int) -> None:
    if start < 1 or end < start or end > max_number(doc_type):
        raise HTTPException(422, "El rango de la secuencia no es válido")


def after_reversal(db: Session, payment: Payment, user, reason: str) -> None:
    """Hook of the payment reversal: a credit note for its receipt (or pending)."""
    document = (
        db.query(FiscalDocument)
        .filter(
            FiscalDocument.payment_id == payment.payment_id,
            FiscalDocument.affected_document_id.is_(None),
            FiscalDocument.status == "issued",
        )
        .first()
    )
    if document is None:
        return
    try:
        with db.begin_nested():
            credit_note(db, document, user, reason)
    except FiscalError as problem:
        event(
            db,
            user,
            document.student_id,
            "fiscal.pending",
            {"credit_note_for": document.ncf, "reason": problem.detail},
        )
