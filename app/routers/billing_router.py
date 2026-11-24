"""«Plan y facturación» of an institution and payment webhooks (Fase 4, block D2)."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_permissions
from app.db.Session import get_db
from app.models.billing_model import Plan
from app.models.user_model import User
from app.services.audit_log import record
from app.services.billing import lifecycle
from app.services.billing.access import allow_while_read_only
from app.services.billing.limits import GB, ceiling, subscription_of, usage
from app.services.billing.providers import SandboxProvider, StripeProvider, provider
from app.services.frontend_url import frontend_base
from app.services.platform import lock_platform
from app.services.write_locks import lock_access

router = APIRouter(prefix="/billing", tags=["billing"])
manager = require_permissions("billing.manage", institutional=True)


class CheckoutRequest(BaseModel):
    plan_code: str = Field(min_length=2, max_length=40)
    interval: str = Field(default="monthly", pattern=r"^(monthly|yearly)$")


class SandboxOutcome(BaseModel):
    token: str = Field(min_length=10, max_length=2000)
    outcome: str = Field(pattern=r"^(paid|failed)$")


class Limit(BaseModel):
    used: float
    limit: float | None = None
    ceiling: float | None = None


class PlanOption(BaseModel):
    code: str
    name: str
    description: str
    currency: str
    monthly_price: str
    yearly_price: str
    max_students: int | None = None
    max_staff: int | None = None
    storage_gb: int | None = None


class BillingOverview(BaseModel):
    plan: PlanOption | None = None
    status: str
    interval: str | None = None
    trial_ends_at: str | None = None
    current_period_end: str | None = None
    provider: str
    online_checkout: bool
    has_payment_method: bool
    students: Limit
    staff: Limit
    storage_gb: Limit
    plans: list[PlanOption]


class Invoice(BaseModel):
    number: str
    date: str | None = None
    amount: str
    currency: str
    status: str
    url: str | None = None


def plan_option(plan: Plan) -> dict:
    return {
        "code": plan.code,
        "name": plan.name,
        "description": plan.description,
        "currency": plan.currency,
        "monthly_price": f"{plan.monthly_price:.2f}",
        "yearly_price": f"{plan.yearly_price:.2f}",
        "max_students": plan.max_students,
        "max_staff": plan.max_staff,
        "storage_gb": plan.storage_gb,
    }


def limit(used: float, value: int | None, scale: float = 1) -> dict:
    return {
        "used": round(used, 2),
        "limit": value,
        "ceiling": ceiling(int(value * scale)) / scale if value is not None else None,
    }


def overview(db: Session, user: User) -> dict:
    subscription = subscription_of(db, user.institution_id)
    counts = usage(db, user.institution_id)
    plan = subscription.plan if subscription else None
    payments = provider()
    plans = (
        db.query(Plan)
        .filter(Plan.public.is_(True), Plan.active.is_(True))
        .order_by(Plan.sort_order, Plan.plan_id)
        .all()
    )
    return {
        "plan": plan_option(plan) if plan else None,
        "status": subscription.status if subscription else "active",
        "interval": subscription.interval if subscription else None,
        "trial_ends_at": _iso(subscription.trial_ends_at) if subscription else None,
        "current_period_end": _iso(subscription.current_period_end) if subscription else None,
        "provider": payments.name,
        "online_checkout": bool(payments.enabled),
        "has_payment_method": bool(subscription and subscription.provider_customer_id),
        "students": limit(counts.students, plan.max_students if plan else None),
        "staff": limit(counts.staff, plan.max_staff if plan else None),
        "storage_gb": limit(counts.storage_bytes / GB, plan.storage_gb if plan else None, GB),
        "plans": [plan_option(item) for item in plans],
    }


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def return_url(request: Request) -> str:
    """Where the provider sends the person back: the page that asked, if it is ours."""
    return f"{frontend_base(request)}/billing"


def require_subscription(db: Session, user: User):
    subscription = subscription_of(db, user.institution_id)
    if subscription is None:
        raise HTTPException(409, "Esta institución no tiene una suscripción. Escribe a Nexo")
    return subscription


class BillingStatus(BaseModel):
    status: str
    trial_ends_at: str | None = None
    days_left: int | None = None
    read_only: bool
    grace_ends_at: str | None = None


@router.get("/status", response_model=BillingStatus)
def billing_status(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """For the notices of every account: trial, overdue payment, read-only mode."""
    from datetime import timedelta

    from app.services.billing.access import BLOCKED_STATUSES
    from app.services.billing.lifecycle import GRACE_DAYS, READ_ONLY_DAYS, now

    subscription = subscription_of(db, user.institution_id)
    if subscription is None:
        return {"status": "active", "read_only": False}
    ends = None
    if subscription.status == "trialing":
        ends = subscription.trial_ends_at
    elif subscription.status == "past_due" and subscription.past_due_since:
        ends = subscription.past_due_since + timedelta(days=GRACE_DAYS)
    elif subscription.status in BLOCKED_STATUSES and subscription.read_only_since:
        ends = subscription.read_only_since + timedelta(days=READ_ONLY_DAYS)
    return {
        "status": subscription.status,
        "trial_ends_at": _iso(subscription.trial_ends_at),
        "days_left": max(0, (ends.date() - now().date()).days) if ends else None,
        "read_only": subscription.status in BLOCKED_STATUSES,
        "grace_ends_at": _iso(ends),
    }


@router.get("/subscription", response_model=BillingOverview)
def get_subscription(db: Session = Depends(get_db), user: User = Depends(manager)):
    return overview(db, user)


@router.post("/checkout")
def checkout(
    data: CheckoutRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(manager),
):
    allow_while_read_only(db)  # paying is how a read-only institution gets back
    lock_access(db)
    subscription = require_subscription(db, user)
    plan = (
        db.query(Plan)
        .filter(Plan.code == data.plan_code, Plan.public.is_(True), Plan.active.is_(True))
        .first()
    )
    if plan is None:
        raise HTTPException(404, "Ese plan no está disponible")
    url = provider().checkout(subscription, plan, data.interval, return_url(request))
    record(
        db,
        user,
        "billing.checkout_started",
        f"plan:{plan.code}",
        f"Pago del plan {plan.name} ({'anual' if data.interval == 'yearly' else 'mensual'})",
    )
    db.commit()
    return {"url": url}


@router.post("/portal")
def portal(request: Request, db: Session = Depends(get_db), user: User = Depends(manager)):
    allow_while_read_only(db)
    lock_access(db)
    subscription = require_subscription(db, user)
    url = provider().portal(subscription, return_url(request))
    record(db, user, "billing.portal_opened", "billing", "Gestión del método de pago")
    db.commit()
    return {"url": url}


@router.get("/invoices", response_model=list[Invoice])
def invoices(db: Session = Depends(get_db), user: User = Depends(manager)):
    subscription = subscription_of(db, user.institution_id)
    if subscription is None:
        return []
    rows = provider().invoices(subscription)
    return [{**row, "date": _iso(row.get("date"))} for row in rows]


def sandbox() -> SandboxProvider:
    payments = provider()
    if not isinstance(payments, SandboxProvider) or not payments.enabled:
        raise HTTPException(404, "El pago de prueba no está disponible")
    return payments


@router.get("/sandbox/session")
def sandbox_session(token: str, db: Session = Depends(get_db), user: User = Depends(manager)):
    payload = sandbox().session(token)
    if payload["institution_id"] != user.institution_id:
        raise HTTPException(403, "Este pago de prueba pertenece a otra institución")
    plan = db.query(Plan).filter(Plan.code == payload["plan_code"]).first()
    if plan is None:
        raise HTTPException(404, "Ese plan no está disponible")
    return {"plan": plan_option(plan), "interval": payload["interval"]}


@router.post("/sandbox/complete", response_model=BillingOverview)
def sandbox_complete(
    data: SandboxOutcome, db: Session = Depends(get_db), user: User = Depends(manager)
):
    """Development and demos only: what a real provider would notify by webhook."""
    payments = sandbox()
    if payments.session(data.token)["institution_id"] != user.institution_id:
        raise HTTPException(403, "Este pago de prueba pertenece a otra institución")
    allow_while_read_only(db)
    lock_platform(db)
    for event in payments.complete(data.token, data.outcome):
        lifecycle.apply(db, payments.name, event)
    record(
        db,
        user,
        "billing.sandbox_payment",
        "billing",
        "Pago de prueba aprobado" if data.outcome == "paid" else "Pago de prueba rechazado",
    )
    db.commit()
    return overview(db, user)


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Signed by Stripe; no session. Retries are harmless (events apply once)."""
    payments = provider()
    if not isinstance(payments, StripeProvider):
        raise HTTPException(404, "Stripe no está configurado")
    body = await request.body()
    events = payments.parse(body, request.headers.get("stripe-signature"))
    lock_platform(db)
    outcomes = [lifecycle.apply(db, payments.name, event) for event in events]
    db.commit()
    return {"received": True, "outcomes": outcomes}
