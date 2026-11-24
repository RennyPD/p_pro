"""Online card payments of families and students (Fase 4, block E)."""

import json
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_user, has_scope, require_permissions
from app.db.Session import get_db
from app.db.tenant import set_tenant, tenant_bypass
from app.models.finance_model import Payment
from app.models.online_payment_model import OnlinePayment, PaymentGatewayConfig
from app.models.student_model import Student
from app.models.user_model import User
from app.pagination import page_query, search
from app.services.audit_log import record
from app.services.business_time import business_day_utc_range
from app.services.finance_workflow import cents, get_account, lock_finance, summary
from app.services.frontend_url import frontend_base
from app.services.payments import intents
from app.services.payments.gateways import GATEWAYS, GatewayResult, gateway_for
from app.services.payments.secrets import decrypt, encrypt, mask
from app.services.rate_limit import PAYMENTS, PUBLIC, per_account, per_address

router = APIRouter(prefix="/online-payments", tags=["online payments"])
finance_manager = require_permissions("finance.manage", institutional=True)


class Share(BaseModel):
    student_id: int
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)


class IntentCreate(BaseModel):
    allocations: list[Share] = Field(min_length=1, max_length=20)


class Completion(BaseModel):
    # The query string the bank sent back to the result page, as received.
    params: dict[str, str] = Field(default_factory=dict)


class GatewayConfigIn(BaseModel):
    enabled: bool
    gateway: str = Field(pattern=r"^(sandbox|azul|cardnet)$")
    merchant_id: str = Field(default="", max_length=60)
    merchant_name: str = Field(default="", max_length=100)
    min_amount: Decimal = Field(default=Decimal("100.00"), ge=1, max_digits=12, decimal_places=2)
    environment: str = Field(default="test", pattern=r"^(test|live)$")
    # Only the secrets being changed: empty keeps the stored value.
    auth_key: str | None = Field(default=None, max_length=200)
    terminal: str | None = Field(default=None, max_length=40)
    merchant_type: str | None = Field(default=None, max_length=40)


def intent_out(db: Session, intent: OnlinePayment) -> dict:
    ids = [int(item) for item in intent.payment_ids.split(",") if item]
    receipts = (
        [row[0] for row in db.query(Payment.receipt_number).filter(Payment.payment_id.in_(ids))]
        if ids
        else []
    )
    return {
        "id": intent.public_id,
        "status": intent.status,
        "amount": f"{intent.amount:.2f}",
        "currency": intent.currency,
        "gateway": intent.gateway,
        "authorization_code": intent.authorization_code,
        "message": intent.response_message,
        "receipts": receipts,
        "created_at": intent.created_at.isoformat(),
    }


@router.get("/options")
def options(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """What this account can pay online (nothing for staff or when disabled)."""
    config = intents.config_of(db)
    enabled = bool(config and config.enabled and gateway_for(config.gateway).enabled)
    students = []
    if enabled:
        for student_id in sorted(intents.payable_students(db, user)):
            balance = summary(get_account(db, student_id)).balance
            student = db.get(Student, student_id)
            students.append(
                {
                    "student_id": student_id,
                    "name": f"{student.first_name} {student.last_name}",
                    "balance": f"{balance:.2f}",
                }
            )
    return {
        "enabled": enabled and bool(students),
        "gateway": config.gateway if enabled else None,
        "min_amount": f"{config.min_amount:.2f}" if config else "100.00",
        "students": students,
    }


@router.post("", dependencies=[Depends(per_account(PAYMENTS))])
def create(
    data: IntentCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    intent = intents.create_intent(
        db, user, [(share.student_id, cents(share.amount)) for share in data.allocations]
    )
    redirect = intents.start(db, intent, f"{frontend_base(request)}/pagos")
    db.commit()
    return {
        "id": intent.public_id,
        "redirect": {"method": redirect.method, "url": redirect.url, "fields": redirect.fields},
    }


def find_intent(db: Session, public_id: str) -> OnlinePayment:
    intent = (
        db.query(OnlinePayment)
        .filter(OnlinePayment.public_id == public_id)
        .execution_options(**tenant_bypass())
        .first()
    )
    if intent is None:
        raise HTTPException(404, "Pago no encontrado")
    return intent


finance_viewer = require_permissions("finance.view", institutional=True)
finance_supervisor = require_permissions("finance.supervise", institutional=True)


class Resolution(BaseModel):
    outcome: str = Field(pattern=r"^(approved|declined)$")
    authorization_code: str | None = Field(default=None, max_length=40)
    reason: str = Field(min_length=5, max_length=250)


def staff_out(db: Session, intent: OnlinePayment, names: dict[int, str]) -> dict:
    shares = json.loads(intent.allocations)
    return {
        **intent_out(db, intent),
        "payer": names.get(intent.payer_user_id, ""),
        "students": [
            {
                "student_id": share["student_id"],
                "name": names.get(-share["student_id"], ""),
                "amount": f"{share['amount_cents'] / 100:.2f}",
            }
            for share in shares
        ],
        "provider_reference": intent.provider_reference,
        "overpaid": intent.overpaid,
        "completed_at": intent.completed_at.isoformat() if intent.completed_at else None,
    }


def names_for(db: Session, intents_: list[OnlinePayment]) -> dict[int, str]:
    """Payer usernames (by user id) and student names (by -student id)."""
    users = {i.payer_user_id for i in intents_}
    students = {s["student_id"] for i in intents_ for s in json.loads(i.allocations)}
    names = {
        row.user_id: row.username
        for row in db.query(User.user_id, User.username).filter(User.user_id.in_(users or {0}))
    }
    for row in db.query(Student.student_id, Student.first_name, Student.last_name).filter(
        Student.student_id.in_(students or {0})
    ):
        names[-row.student_id] = f"{row.first_name} {row.last_name}"
    return names


@router.get("")
def list_payments(
    response: Response,
    status: str | None = Query(
        None, pattern=r"^(created|pending|approved|declined|expired|error)$"
    ),
    day: date | None = None,
    q: str | None = Query(None, max_length=60),
    skip: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    _user: User = Depends(finance_viewer),
):
    """Reconciliation: every online payment with the bank's references."""
    query = db.query(OnlinePayment).order_by(OnlinePayment.online_payment_id.desc())
    if status:
        query = query.filter(OnlinePayment.status == status)
    if day:
        start, end = business_day_utc_range(day)
        query = query.filter(OnlinePayment.created_at >= start, OnlinePayment.created_at < end)
    query = search(
        query, q, OnlinePayment.public_id, OnlinePayment.authorization_code,
        OnlinePayment.provider_reference,
    )  # fmt: skip
    rows = page_query(query, response, skip, limit)
    names = names_for(db, rows)
    return [staff_out(db, row, names) for row in rows]


@router.get("/report/daily")
def daily_report(day: date, db: Session = Depends(get_db), _user: User = Depends(finance_viewer)):
    """Totals of one business day, to match the bank's settlement."""
    from sqlalchemy import func

    start, end = business_day_utc_range(day)
    rows = (
        db.query(
            OnlinePayment.status,
            OnlinePayment.gateway,
            func.count(),
            func.sum(OnlinePayment.amount),
        )
        .filter(OnlinePayment.created_at >= start, OnlinePayment.created_at < end)
        .group_by(OnlinePayment.status, OnlinePayment.gateway)
        .all()
    )
    return {
        "day": day.isoformat(),
        "rows": [
            {
                "status": status,
                "gateway": gateway,
                "count": count,
                "amount": f"{(total or 0):.2f}",
            }
            for status, gateway, count, total in rows
        ],
        "approved_amount": f"{sum((r[3] or 0) for r in rows if r[0] == 'approved'):.2f}",
    }


@router.post("/{public_id}/resolve")
def resolve(
    public_id: str,
    data: Resolution,
    db: Session = Depends(get_db),
    user: User = Depends(finance_supervisor),
):
    """The bank's portal shows what happened to a payment Nexo never heard back about."""
    lock_finance(db)
    intent = db.query(OnlinePayment).filter(OnlinePayment.public_id == public_id).first()
    if intent is None:
        raise HTTPException(404, "Pago no encontrado")
    if intent.status in ("approved", "declined"):
        raise HTTPException(409, "Este pago ya tiene un resultado del banco")
    if data.outcome == "approved" and not (data.authorization_code or "").strip():
        raise HTTPException(422, "Escribe el código de autorización que muestra el banco")
    result = GatewayResult(
        status=data.outcome,
        amount_cents=None,
        authorization_code=(data.authorization_code or "").strip() or None,
        response_code="MANUAL",
        message=f"Resuelto en Nexo: {data.reason.strip()}",
    )
    intents.apply_result(db, intent, result, actor=user)
    record(
        db,
        user,
        "online_payment.resolved",
        f"online_payment:{intent.public_id}",
        f"{data.outcome}; autorización {result.authorization_code or '—'}; {data.reason.strip()}",
    )
    db.commit()
    names = names_for(db, [intent])
    return staff_out(db, intent, names)


@router.get("/{public_id}")
def get_intent(
    public_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    intent = db.query(OnlinePayment).filter(OnlinePayment.public_id == public_id).first()
    if intent is None or (
        intent.payer_user_id != user.user_id and not has_scope(user, "finance.view")
    ):
        raise HTTPException(404, "Pago no encontrado")
    return intent_out(db, intent)


@router.post("/{public_id}/complete", dependencies=[Depends(per_address(PUBLIC))])
def complete(public_id: str, data: Completion, db: Session = Depends(get_db)):
    """The bank sent the payer back: verify its signed answer and post the payment.

    Public on purpose: the session may have expired while paying. The answer
    is trusted only after its signature (or a server-to-server query) checks.
    """
    intent = find_intent(db, public_id)
    set_tenant(db, intent.institution_id)
    lock_finance(db)
    db.refresh(intent)
    if intent.status not in ("approved", "declined"):
        result = intents.verify(db, intent, data.params)
        intents.apply_result(db, intent, result)
        db.commit()
    return intent_out(db, intent)


# --- The institution's gateway (block E3) --------------------------------------


def config_out(config: PaymentGatewayConfig | None) -> dict:
    if config is None:
        return {
            "enabled": False,
            "gateway": "sandbox",
            "merchant_id": "",
            "merchant_name": "",
            "min_amount": "100.00",
            "environment": "test",
            "auth_key": "",
            "terminal": "",
            "merchant_type": "",
            "gateways": sorted(GATEWAYS),
        }
    secrets = decrypt(config.secrets) if config.secrets else {}
    return {
        "enabled": config.enabled,
        "gateway": config.gateway,
        "merchant_id": config.merchant_id,
        "merchant_name": config.merchant_name,
        "min_amount": f"{config.min_amount:.2f}",
        "environment": secrets.get("environment", "test"),
        "auth_key": mask(secrets.get("auth_key")),
        "terminal": mask(secrets.get("terminal")),
        "merchant_type": secrets.get("merchant_type", ""),
        "gateways": sorted(GATEWAYS),
    }


@router.get("/config/gateway")
def get_config(db: Session = Depends(get_db), _user: User = Depends(finance_manager)):
    return config_out(intents.config_of(db))


@router.put("/config/gateway")
def save_config(
    data: GatewayConfigIn, db: Session = Depends(get_db), user: User = Depends(finance_manager)
):
    lock_finance(db)
    config = intents.config_of(db) or PaymentGatewayConfig(secrets="")
    db.add(config)
    secrets = decrypt(config.secrets) if config.secrets else {}
    for key in ("auth_key", "terminal", "merchant_type"):
        value = getattr(data, key)
        if value:
            secrets[key] = value.strip()
    secrets["environment"] = data.environment
    if (
        data.enabled
        and data.gateway == "azul"
        and not (data.merchant_id and secrets.get("auth_key"))
    ):
        raise HTTPException(422, "Azul necesita el número de comercio y la AuthKey")
    if (
        data.enabled
        and data.gateway == "cardnet"
        and not (data.merchant_id and secrets.get("terminal"))
    ):
        raise HTTPException(422, "CardNet necesita el número de comercio y la terminal")
    config.enabled = data.enabled
    config.gateway = data.gateway
    config.merchant_id = data.merchant_id.strip()
    config.merchant_name = data.merchant_name.strip()
    config.min_amount = data.min_amount
    config.secrets = encrypt(secrets)
    config.updated_at = intents.now()
    config.updated_by = user.user_id
    db.flush()
    changed = [key for key in ("auth_key", "terminal") if getattr(data, key)]
    record(
        db,
        user,
        "online_payments.configured",
        f"gateway:{data.gateway}",
        json.dumps(
            {
                "enabled": data.enabled,
                "merchant_id": config.merchant_id,
                "environment": data.environment,
                "secrets_changed": changed,
            },
            ensure_ascii=False,
        ),
    )
    db.commit()
    return config_out(config)
