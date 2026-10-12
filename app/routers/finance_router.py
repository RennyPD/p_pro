import base64
import binascii
from datetime import UTC, date
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth import ensure_student_access, get_current_user, require_permissions
from app.db.database import settings
from app.db.Session import get_db
from app.models.finance_model import (
    BillingConcept,
    CashClosing,
    Charge,
    FinanceEvent,
    FinancialAdjustment,
    Installment,
    Payment,
    PaymentPlan,
    StudentAccount,
    TransferRequest,
)
from app.models.student_model import Student
from app.models.user_model import User
from app.schemas.finance_schema import (
    AccountUpdate,
    AdjustmentCreate,
    BillingConceptCreate,
    ChargeCreate,
    FinanceAccountListItem,
    PaymentCreate,
    PaymentPlanCreate,
    ReasonRequest,
    SimulationCreate,
    StudentFinanceSummary,
    TransferCreate,
    TransferReview,
)
from app.services.finance_workflow import (
    CREDIT_KINDS,
    RD,
    add_months,
    business_date,
    cents,
    check_open_day,
    credits,
    event,
    get_account,
    lock_finance,
    money,
    next_due,
    now,
    plan_summary,
    post_payment,
    summary,
    writable_account,
)
from app.services.pdf_service import simple_pdf

router = APIRouter(prefix="/finance", tags=["finance"])
finance_manager = require_permissions("finance.manage", fallback_roles=("admin",))
# Kept for document and report consumers; reads never create persisted accounts.
get_or_create_account = get_account
build_summary = summary


def accessible(user, student_id):
    if user.role.name.casefold() == "admin":
        return
    ensure_student_access(user, student_id)


def result(db, account):
    db.commit()
    db.expire_all()
    return summary(db.get(StudentAccount, account.student_account_id))


@router.get("/options")
def options(user: User = Depends(get_current_user)):
    return {
        "currency": "DOP",
        "gateway_enabled": False,
        "transfer_instructions": settings.finance_transfer_instructions,
        "simulator_enabled": settings.finance_simulator_enabled
        and user.role.name.casefold() == "admin",
    }


@router.get(
    "/accounts",
    response_model=list[FinanceAccountListItem],
    dependencies=[Depends(finance_manager)],
)
def list_accounts(db: Session = Depends(get_db)):
    return [
        FinanceAccountListItem(
            student_id=s.student_id,
            enrollment_number=s.enrollment_number,
            student_name=s.full_name,
            balance=(value := summary(get_account(db, s.student_id))).balance,
            overdue_balance=value.overdue_balance,
        )
        for s in db.query(Student).order_by(Student.enrollment_number)
    ]


@router.get("/students/{student_id}", response_model=StudentFinanceSummary)
def student_finance(
    student_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    accessible(user, student_id)
    return summary(get_account(db, student_id))


@router.put("/students/{student_id}/account", response_model=StudentFinanceSummary)
def update_account(
    student_id: int,
    data: AccountUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(finance_manager),
):
    account = writable_account(db, student_id)
    before = {"cutoff_day": account.cutoff_day, "due_day": account.due_day}
    account.cutoff_day, account.due_day = data.cutoff_day, data.due_day
    event(db, user, student_id, "account.updated", {"before": before, "after": data.model_dump()})
    return result(db, account)


@router.post("/students/{student_id}/charges", response_model=StudentFinanceSummary)
def add_charge(
    student_id: int,
    data: ChargeCreate,
    db: Session = Depends(get_db),
    user: User = Depends(finance_manager),
):
    account = writable_account(db, student_id)
    item = Charge(
        student_account_id=account.student_account_id,
        description=data.description.strip(),
        amount=money(cents(data.amount)),
        due_date=data.due_date or next_due(account),
        created_by=user.user_id,
    )
    if len(item.description) < 2:
        raise HTTPException(422, "El concepto no puede estar vacío")
    db.add(item)
    db.flush()
    event(
        db,
        user,
        student_id,
        "charge.created",
        {
            "charge_id": item.charge_id,
            "description": item.description,
            "amount_cents": cents(item.amount),
            "due_date": item.due_date,
        },
    )
    return result(db, account)


@router.post("/students/{student_id}/payments", response_model=StudentFinanceSummary)
def add_payment(
    student_id: int,
    data: PaymentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(finance_manager),
):
    account = writable_account(db, student_id)
    if data.idempotency_key:
        existing = db.query(Payment).filter_by(idempotency_key=data.idempotency_key).first()
        if existing:
            if (
                existing.student_account_id != account.student_account_id
                or cents(existing.amount) != cents(data.amount)
                or existing.reference != data.reference
                or existing.note != data.note
                or existing.method != data.method
            ):
                raise HTTPException(409, "La clave de operación ya corresponde a otro pago")
            db.rollback()
            return summary(get_account(db, student_id))
    post_payment(db, account, data, user, key=data.idempotency_key)
    return result(db, account)


@router.post("/students/{student_id}/adjustments", response_model=StudentFinanceSummary)
def add_adjustment(
    student_id: int,
    data: AdjustmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(finance_manager),
):
    account = writable_account(db, student_id)
    if data.kind in CREDIT_KINDS and cents(data.amount) > cents(summary(account).balance):
        raise HTTPException(422, "El descuento o crédito no puede superar el balance")
    item = FinancialAdjustment(
        student_account_id=account.student_account_id,
        kind=data.kind,
        description=data.description.strip(),
        amount=money(cents(data.amount)),
        due_date=(data.due_date or business_date()) if data.kind not in CREDIT_KINDS else None,
        created_by=user.user_id,
    )
    if len(item.description) < 2:
        raise HTTPException(422, "El motivo no puede estar vacío")
    db.add(item)
    db.flush()
    event(
        db,
        user,
        student_id,
        "adjustment.created",
        {
            "adjustment_id": item.adjustment_id,
            "kind": item.kind,
            "description": item.description,
            "amount_cents": cents(item.amount),
            "due_date": item.due_date,
        },
    )
    return result(db, account)


@router.post(
    "/students/{student_id}/transactions/{kind}/{identifier}/reverse",
    response_model=StudentFinanceSummary,
)
def reverse(
    student_id: int,
    kind: str,
    identifier: int,
    data: ReasonRequest,
    db: Session = Depends(get_db),
    user: User = Depends(finance_manager),
):
    account = writable_account(db, student_id)
    model = {"payment": Payment, "charge": Charge, "adjustment": FinancialAdjustment}.get(kind)
    item = db.get(model, identifier) if model else None
    if not item or item.student_account_id != account.student_account_id:
        raise HTTPException(404, "Movimiento no encontrado en esta cuenta")
    if item.status != "posted":
        raise HTTPException(409, "El movimiento ya fue reversado")
    if any(p.active for p in account.payment_plans):
        raise HTTPException(
            409, "Cancela primero el plan activo para revisar el balance y rehacer sus cuotas"
        )
    if kind == "payment":
        check_open_day(db)
        check_open_day(db, business_date(item.paid_at))
        item.reversed_by, item.reversed_at = user.user_id, now()
    before = summary(account).balance
    item.status, item.reversal_reason = "reversed", data.reason
    if cents(summary(account).balance) < 0:
        raise HTTPException(
            409,
            "El reverso dejaría saldo a favor; revisa primero los pagos y créditos relacionados",
        )
    event(
        db,
        user,
        student_id,
        "transaction.reversed",
        {
            "kind": kind,
            "id": identifier,
            "reason": data.reason,
            "balance_before": before,
            "balance_after": summary(account).balance,
        },
    )
    return result(db, account)


@router.post("/students/{student_id}/payment-plans")
def create_payment_plan(
    student_id: int,
    data: PaymentPlanCreate,
    db: Session = Depends(get_db),
    user: User = Depends(finance_manager),
):
    account = writable_account(db, student_id)
    balance = cents(summary(account).balance)
    if balance <= 0:
        raise HTTPException(409, "La cuenta no tiene balance pendiente")
    if any(p.active for p in account.payment_plans):
        raise HTTPException(409, "Ya existe un plan activo; cancélalo antes de crear otro")
    if data.first_due_date < business_date():
        raise HTTPException(422, "La primera cuota no puede vencer en el pasado")
    if balance < data.installments:
        raise HTTPException(422, "El monto es insuficiente para cuotas de al menos un centavo")
    plan = PaymentPlan(
        student_account_id=account.student_account_id,
        name=data.name.strip(),
        active=True,
        credit_baseline=money(credits(account)),
        created_by=user.user_id,
        created_at=now(),
    )
    db.add(plan)
    db.flush()
    base, remainder = divmod(balance, data.installments)
    for index in range(data.installments):
        db.add(
            Installment(
                payment_plan_id=plan.payment_plan_id,
                due_date=add_months(data.first_due_date, index),
                amount=money(base + (1 if index < remainder else 0)),
                paid=False,
            )
        )
    event(
        db,
        user,
        student_id,
        "plan.created",
        {
            "plan_id": plan.payment_plan_id,
            "name": plan.name,
            "amount_cents": balance,
            "installments": data.installments,
            "first_due_date": data.first_due_date,
        },
    )
    db.commit()
    return {"payment_plan_id": plan.payment_plan_id, "installments": data.installments}


@router.get("/students/{student_id}/payment-plans")
def list_plans(
    student_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    accessible(user, student_id)
    account = get_account(db, student_id)
    return [
        plan_summary(account, p)
        for p in sorted(account.payment_plans, key=lambda p: p.payment_plan_id, reverse=True)
    ]


@router.post("/students/{student_id}/payment-plans/{plan_id}/cancel")
def cancel_plan(
    student_id: int,
    plan_id: int,
    data: ReasonRequest,
    db: Session = Depends(get_db),
    user: User = Depends(finance_manager),
):
    account = writable_account(db, student_id)
    plan = next((p for p in account.payment_plans if p.payment_plan_id == plan_id), None)
    if not plan or not plan.active:
        raise HTTPException(409, "Plan no encontrado o ya cancelado")
    plan.credit_snapshot = money(max(credits(account) - cents(plan.credit_baseline), 0))
    plan.active = False
    event(db, user, student_id, "plan.cancelled", {"plan_id": plan_id, "reason": data.reason})
    db.commit()
    return {"message": "Plan cancelado; los movimientos y la deuda se conservan"}


def transfer_out(item):
    return {
        key: getattr(item, key)
        for key in (
            "transfer_request_id",
            "student_id",
            "reference",
            "bank",
            "note",
            "status",
            "submitted_at",
            "reviewed_at",
            "review_reason",
            "payment_id",
        )
    } | {"amount": money(item.amount_cents)}


@router.post("/students/{student_id}/transfers")
def submit_transfer(
    student_id: int,
    data: TransferCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    accessible(user, student_id)
    if not settings.finance_transfer_instructions.strip():
        raise HTTPException(409, "La institución aún no configuró sus instrucciones bancarias")
    account = writable_account(db, student_id)
    if cents(data.amount) > cents(summary(account).balance):
        raise HTTPException(422, "La transferencia supera el balance pendiente")
    if (
        db.query(TransferRequest).filter_by(reference=data.reference).first()
        or db.query(Payment).filter_by(reference=data.reference).first()
    ):
        raise HTTPException(409, "Referencia ya registrada")
    try:
        proof = base64.b64decode(data.proof_base64, validate=True)
    except (ValueError, binascii.Error):
        raise HTTPException(422, "Comprobante inválido")
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
    item = TransferRequest(
        student_id=student_id,
        amount_cents=cents(data.amount),
        reference=data.reference,
        bank=data.bank,
        note=data.note,
        proof=proof,
        proof_type=mime,
        submitted_by=user.user_id,
    )
    db.add(item)
    db.flush()
    event(
        db,
        user,
        student_id,
        "transfer.submitted",
        {
            "request_id": item.transfer_request_id,
            "reference": item.reference,
            "amount_cents": item.amount_cents,
        },
    )
    db.commit()
    return transfer_out(item)


@router.get("/students/{student_id}/transfers")
def transfers(
    student_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    accessible(user, student_id)
    get_account(db, student_id)
    return [
        transfer_out(t)
        for t in db.query(TransferRequest)
        .filter_by(student_id=student_id)
        .order_by(TransferRequest.transfer_request_id.desc())
    ]


@router.get("/transfers/{identifier}/proof")
def proof(identifier: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.get(TransferRequest, identifier)
    if not item:
        raise HTTPException(404, "Comprobante no encontrado")
    accessible(user, item.student_id)
    ext = {"application/pdf": "pdf", "image/png": "png", "image/jpeg": "jpg"}[item.proof_type]
    return Response(
        item.proof,
        media_type=item.proof_type,
        headers={
            "Content-Disposition": f'attachment; filename="comprobante-{identifier}.{ext}"',
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox",
            "Cache-Control": "no-store",
        },
    )


@router.post("/transfers/{identifier}/review")
def review_transfer(
    identifier: int,
    data: TransferReview,
    db: Session = Depends(get_db),
    user: User = Depends(finance_manager),
):
    lock_finance(db)
    item = db.get(TransferRequest, identifier)
    if not item:
        raise HTTPException(404, "Transferencia no encontrada")
    if item.status != "pending":
        raise HTTPException(409, "La solicitud ya fue revisada")
    account = get_account(db, item.student_id, write=True)
    if data.approve:
        payment = post_payment(
            db,
            account,
            SimpleNamespace(
                amount=money(item.amount_cents), reference=item.reference, note=item.note
            ),
            user,
            method="transfer",
            key=f"transfer:{identifier}",
        )
        item.payment_id = payment.payment_id
    item.status = "approved" if data.approve else "rejected"
    item.review_reason, item.reviewed_by, item.reviewed_at = data.reason, user.user_id, now()
    event(
        db,
        user,
        item.student_id,
        "transfer.reviewed",
        {
            "request_id": identifier,
            "status": item.status,
            "reason": data.reason,
            "payment_id": item.payment_id,
        },
    )
    db.commit()
    return transfer_out(item)


@router.get("/payments/{identifier}/receipt.pdf")
def receipt(identifier: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.get(Payment, identifier)
    if not item:
        raise HTTPException(404, "Pago no encontrado")
    account = db.get(StudentAccount, item.student_account_id)
    accessible(user, account.student_id)
    lines = [
        "RECIBO INTERNO - NO ES COMPROBANTE FISCAL",
        f"Recibo: {item.receipt_number or 'Legado sin numeración'}",
        f"Estudiante: {account.student.full_name}",
        f"Matricula: {account.student.enrollment_number}",
        f"Monto RD$: {item.amount:.2f}",
        f"Referencia: {item.reference}",
        f"Metodo: {item.method}",
        f"Fecha local: {item.paid_at.replace(tzinfo=UTC).astimezone(RD).isoformat()}",
        f"Estado: {item.status}",
        f"Reverso: {item.reversal_reason or '-'}",
    ]
    return Response(
        simple_pdf("RECIBO DE PAGO INTERNO", lines),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="recibo-{identifier}.pdf"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/students/{student_id}/history", dependencies=[Depends(finance_manager)])
def history(student_id: int, db: Session = Depends(get_db)):
    get_account(db, student_id)
    return [
        {
            "id": e.finance_event_id,
            "action": e.action,
            "detail": e.detail,
            "created_at": e.created_at,
            "actor": db.get(User, e.user_id).username,
        }
        for e in db.query(FinanceEvent)
        .filter_by(student_id=student_id)
        .order_by(FinanceEvent.finance_event_id.desc())
    ]


@router.post("/students/{student_id}/simulate")
def simulate(
    student_id: int,
    data: SimulationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(finance_manager),
):
    if not settings.finance_simulator_enabled:
        raise HTTPException(409, "Simulador deshabilitado")
    get_account(db, student_id)
    # Intentionally no Payment, TransferRequest or ledger entries.
    return {
        "simulation": True,
        "real_money": False,
        "outcome": data.outcome,
        "amount": str(data.amount),
        "currency": "DOP",
        "balance_changed": False,
    }


@router.get("/billing-concepts", dependencies=[Depends(finance_manager)])
def billing_concepts(db: Session = Depends(get_db)):
    return db.query(BillingConcept).order_by(BillingConcept.name).all()


@router.post("/billing-concepts")
def create_billing_concept(
    data: BillingConceptCreate, db: Session = Depends(get_db), user: User = Depends(finance_manager)
):
    item = BillingConcept(
        **(data.model_dump() | {"amount": money(cents(data.amount)), "name": data.name.strip()})
    )
    db.add(item)
    event(
        db,
        user,
        None,
        "concept.created",
        {"name": item.name, "amount_cents": cents(item.amount), "frequency": item.frequency},
    )
    db.commit()
    db.refresh(item)
    return item


@router.get("/cash-closings", dependencies=[Depends(finance_manager)])
def closings(db: Session = Depends(get_db)):
    return db.query(CashClosing).order_by(CashClosing.closing_date.desc()).all()


@router.post("/cash-closings/{closing_date}")
def close_cash_day(
    closing_date: date,
    db: Session = Depends(get_db),
    user: User = Depends(finance_manager),
):
    lock_finance(db)
    if closing_date > business_date():
        raise HTTPException(422, "No puedes cerrar una fecha futura")
    check_open_day(db, closing_date)
    payments = [
        p
        for p in db.query(Payment).all()
        if business_date(p.paid_at) == closing_date and p.status == "posted"
    ]
    item = CashClosing(
        closing_date=closing_date,
        total_payments=money(sum(cents(p.amount) for p in payments)),
        payment_count=len(payments),
        cash_total=money(sum(cents(p.amount) for p in payments if p.method == "cash")),
        transfer_total=money(sum(cents(p.amount) for p in payments if p.method == "transfer")),
        closed_by=user.user_id,
    )
    db.add(item)
    event(
        db,
        user,
        None,
        "cash.closed",
        {
            "date": closing_date,
            "total": item.total_payments,
            "cash": item.cash_total,
            "transfer": item.transfer_total,
            "legacy": money(sum(cents(p.amount) for p in payments if p.method == "legacy")),
        },
    )
    db.commit()
    db.refresh(item)
    return item
