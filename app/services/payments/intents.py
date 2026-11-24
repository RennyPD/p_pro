"""Online payment intents: creation, the gateway's answer and posting (Fase 4, block E1).

- The amount is decided by the server (never by the browser): each child's
  share must be at most its pending balance and the total at least the
  institution's minimum.
- Only payers pay online: a student who may see their own finances, or a
  guardian whose link allows finances. Staff use the cash register.
- An approved answer posts one payment per child (method ``online``) once,
  even if the bank's redirect is repeated. The card is already charged, so it
  is posted even after the day's cash closing or above a balance that changed
  in the meantime (the intent is then marked ``overpaid`` for the cashier).
"""

import json
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.online_payment_model import OnlinePayment, PaymentGatewayConfig
from app.models.user_model import User
from app.services.finance_workflow import (
    cents,
    event,
    get_account,
    lock_finance,
    money,
    post_payment,
    summary,
)
from app.services.payments.gateways import GatewayResult, gateway_for
from app.services.payments.secrets import decrypt

INTENT_MINUTES = 60
STAFF_ONLY = "Los pagos en línea son para familias y estudiantes; en la institución usa la caja"
DISABLED = "La institución aún no recibe pagos en línea"


def now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def config_of(db: Session) -> PaymentGatewayConfig | None:
    return db.query(PaymentGatewayConfig).first()


def active_config(db: Session) -> PaymentGatewayConfig:
    config = config_of(db)
    if config is None or not config.enabled:
        raise HTTPException(409, DISABLED)
    if not gateway_for(config.gateway).enabled:
        raise HTTPException(409, DISABLED)
    return config


def payable_students(db: Session, user: User) -> set[int]:
    """Children (or the student themself) this account may pay for online."""
    from app.auth import guardian_student_ids
    from app.services.institution_profile import student_sees_own_finance

    if user.guardian_id is not None:
        return set(guardian_student_ids(db, user, "finance"))
    if user.student_id is not None and student_sees_own_finance(db, user.student_id):
        return {user.student_id}
    return set()


def create_intent(db: Session, user: User, shares: list[tuple[int, int]]) -> OnlinePayment:
    """``shares``: [(student_id, amount in cents)]; validated against the balances."""
    config = active_config(db)
    allowed = payable_students(db, user)
    if not allowed:
        raise HTTPException(403, STAFF_ONLY)
    students = [student for student, _ in shares]
    if len(students) != len(set(students)):
        raise HTTPException(422, "Cada estudiante aparece una sola vez en el pago")
    if not set(students) <= allowed:
        raise HTTPException(403, "Solo puedes pagar la cuenta de tus estudiantes vinculados")
    lock_finance(db)
    for student, amount in shares:
        if amount <= 0:
            raise HTTPException(422, "Cada monto debe ser mayor que cero")
        if amount > cents(summary(get_account(db, student)).balance):
            raise HTTPException(422, "El pago supera el balance pendiente de un estudiante")
    total = sum(amount for _, amount in shares)
    if total < cents(config.min_amount):
        raise HTTPException(422, f"El pago en línea mínimo es RD${config.min_amount:,.2f}")
    intent = OnlinePayment(
        public_id=uuid.uuid4().hex,
        payer_user_id=user.user_id,
        gateway=config.gateway,
        amount=money(total),
        currency="DOP",
        status="created",
        allocations=json.dumps(
            [{"student_id": student, "amount_cents": amount} for student, amount in shares]
        ),
        created_at=now(),
        expires_at=now() + timedelta(minutes=INTENT_MINUTES),
        payment_ids="",
        overpaid=False,
    )
    db.add(intent)
    db.flush()
    event(
        db,
        user,
        students[0],
        "online_payment.created",
        {"online_payment": intent.public_id, "amount_cents": total, "students": students},
    )
    return intent


def start(db: Session, intent: OnlinePayment, return_url: str):
    config = active_config(db)
    redirect = gateway_for(intent.gateway).start(
        intent, config, decrypt(config.secrets), return_url
    )
    intent.status = "pending"
    return redirect


def verify(db: Session, intent: OnlinePayment, params: dict) -> GatewayResult:
    config = config_of(db)
    if config is None:
        raise HTTPException(409, DISABLED)
    return gateway_for(intent.gateway).verify(params, intent, config, decrypt(config.secrets))


def apply_result(db: Session, intent: OnlinePayment, result: GatewayResult, actor=None) -> str:
    """Record the gateway's answer once; post the payments when approved."""
    if intent.status in ("approved", "declined"):
        return intent.status  # a repeated redirect changes nothing
    # "expired" and "error" may still receive the bank's (late) answer.
    expected = cents(intent.amount)
    if result.status == "approved" and result.amount_cents not in (None, expected):
        intent.status = "error"
        intent.response_message = "El monto aprobado no coincide con el pago"
        raise HTTPException(400, "El monto aprobado por el banco no coincide con el pago")
    lock_finance(db)
    payer = actor or db.get(User, intent.payer_user_id)
    intent.authorization_code = result.authorization_code
    intent.provider_reference = result.provider_reference or intent.provider_reference
    intent.response_code = result.response_code
    intent.response_message = (result.message or "")[:250] or None
    intent.completed_at = now()
    shares = json.loads(intent.allocations)
    if result.status != "approved":
        intent.status = "declined" if result.status == "declined" else "error"
        event(
            db,
            payer,
            shares[0]["student_id"],
            "online_payment.declined",
            {"online_payment": intent.public_id, "message": intent.response_message},
        )
        return intent.status
    payments = []
    for index, share in enumerate(shares, start=1):
        account = get_account(db, share["student_id"], write=True)
        account.ledger_version += 1
        if share["amount_cents"] > cents(summary(account).balance):
            intent.overpaid = True
        suffix = f" ({index}/{len(shares)})" if len(shares) > 1 else ""
        reference = f"EN LÍNEA {intent.gateway.upper()} {result.authorization_code or intent.public_id[:10]}"
        payment = post_payment(
            db,
            account,
            SimpleNamespace(
                amount=money(share["amount_cents"]),
                reference=f"{reference}{suffix}"[:100],
                note=f"Pago en línea {intent.public_id[:12]}",
            ),
            payer,
            method="online",
            online=True,
        )
        payments.append(payment)
    intent.status = "approved"
    intent.payment_ids = ",".join(str(payment.payment_id) for payment in payments)
    return intent.status


def expire_stale(db: Session, moment: datetime | None = None) -> dict[str, int]:
    """Intents nobody came back from: ask the bank first, then mark them expired.

    Runs per institution (``for_each_institution``). An expired intent can still
    be approved later by the bank's answer or by a supervisor (block E5).
    """
    moment = moment or now()
    counts = {"approved": 0, "declined": 0, "expired": 0}
    config = config_of(db)
    stale = (
        db.query(OnlinePayment)
        .filter(
            OnlinePayment.status.in_(("created", "pending")),
            OnlinePayment.expires_at <= moment,
        )
        .all()
    )
    for intent in stale:
        result = None
        if config is not None:
            try:
                result = gateway_for(intent.gateway).query(intent, config, decrypt(config.secrets))
            except HTTPException:
                result = None  # the bank did not answer: try again next time
        if result is not None:
            status = apply_result(db, intent, result)
            counts[status] = counts.get(status, 0) + 1
            continue
        intent.status = "expired"
        intent.completed_at = moment
        counts["expired"] += 1
    return counts
