"""Applies payment events to subscriptions (Fase 4, block D2).

Idempotent (each provider event once, recorded in ``billing_events``) and
order-safe (an event older than the last one applied never undoes it).

- checkout.completed: the chosen plan, active, payment references saved.
- payment.succeeded: active again; overdue and read-only marks cleared.
- payment.failed: trial or active -> past_due (block D3 counts the grace days).
- subscription.canceled: read_only (the institution can still read and export).
"""

from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.billing_model import BillingEvent, Plan, Subscription
from app.models.institution_model import Institution
from app.services.billing.providers import BillingEventData
from app.services.platform import platform_record


def now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def find_subscription(db: Session, event: BillingEventData) -> Subscription | None:
    query = db.query(Subscription)
    if event.institution_id is not None:
        return query.filter(Subscription.institution_id == event.institution_id).first()
    if event.subscription_id:
        found = query.filter(Subscription.provider_subscription_id == event.subscription_id).first()
        if found:
            return found
    if event.customer_id:
        return query.filter(Subscription.provider_customer_id == event.customer_id).first()
    return None


def apply(db: Session, provider: str, event: BillingEventData) -> str:
    """Apply one event; returns what happened (for the log and the audit)."""
    subscription = find_subscription(db, event)
    record = BillingEvent(
        provider=provider,
        event_id=event.event_id,
        kind=event.kind,
        institution_id=subscription.institution_id if subscription else None,
        received_at=now(),
    )
    try:
        with db.begin_nested():
            db.add(record)
            db.flush()
    except IntegrityError:
        return "repetido"
    if subscription is None:
        record.outcome = "sin suscripción asociada"
        return record.outcome
    from app.db.tenant import current_tenant, set_tenant

    if current_tenant(db) is None:  # webhooks: act inside the institution (its notices)
        set_tenant(db, subscription.institution_id)
    if subscription.last_event_at and event.occurred_at < subscription.last_event_at:
        record.outcome = "anterior al último aplicado; ignorado"
        return record.outcome

    before = subscription.status
    if event.kind == "checkout.completed":
        plan = db.query(Plan).filter(Plan.code == event.plan_code).first()
        if plan is not None:
            subscription.plan_id = plan.plan_id
        subscription.interval = event.interval or subscription.interval
        subscription.provider = provider
        subscription.provider_customer_id = event.customer_id or subscription.provider_customer_id
        subscription.provider_subscription_id = (
            event.subscription_id or subscription.provider_subscription_id
        )
        _activate(subscription, event)
    elif event.kind == "payment.succeeded":
        _activate(subscription, event)
    elif event.kind == "payment.failed":
        if subscription.status in ("trialing", "active"):
            subscription.status = "past_due"
            subscription.past_due_since = subscription.past_due_since or event.occurred_at
            notify(db, "past_due", subscription, now())
    elif event.kind == "subscription.canceled":
        subscription.status = "read_only"
        subscription.canceled_at = event.occurred_at
        subscription.read_only_since = subscription.read_only_since or event.occurred_at
    subscription.last_event_at = event.occurred_at
    subscription.updated_at = now()
    db.flush()
    db.refresh(subscription)
    record.outcome = f"{before} → {subscription.status}"
    platform_record(
        db,
        None,
        f"billing.{event.kind}",
        f"institution:{subscription.institution_id}",
        f"{provider}: {record.outcome}; plan {subscription.plan.name}",
    )
    return record.outcome


def _activate(subscription: Subscription, event: BillingEventData) -> None:
    from sqlalchemy.orm import object_session

    lift_billing_suspension(object_session(subscription), subscription.institution_id)
    subscription.status = "active"
    subscription.past_due_since = None
    subscription.read_only_since = None
    subscription.canceled_at = None
    subscription.trial_ends_at = None
    if event.period_end:
        subscription.current_period_end = event.period_end


# --- Daily lifecycle (Fase 4, block D3; decisions of 25/11/2026) -----------------

GRACE_DAYS = 7  # past_due with full access
READ_ONLY_DAYS = 30  # then suspended
TRIAL_REMINDERS = (7, 3, 1)  # days before the trial ends
BILLING_SUSPENSION = "Suspensión automática por falta de pago"


def advance(db: Session, moment: datetime | None = None) -> list[str]:
    """Move the active institution's subscription along; send its notices.

    Runs in a tenant session (``for_each_institution``); idempotent.
    """
    from datetime import timedelta

    from app.db.tenant import current_tenant

    moment = moment or now()
    institution_id = current_tenant(db)
    subscription = (
        db.query(Subscription).filter(Subscription.institution_id == institution_id).first()
    )
    if subscription is None:
        return []
    changes = []

    def move(status: str, notice: str) -> None:
        before = subscription.status
        subscription.status = status
        subscription.updated_at = moment
        changes.append(f"{before} → {status}")
        platform_record(
            db,
            None,
            f"billing.{status}",
            f"institution:{institution_id}",
            f"Automático: {before} → {status}",
        )
        notify(db, notice, subscription, moment)

    if subscription.status == "trialing" and subscription.trial_ends_at:
        left = (subscription.trial_ends_at.date() - moment.date()).days
        if subscription.trial_ends_at <= moment:
            subscription.past_due_since = subscription.trial_ends_at
            move("past_due", "trial_ended")
        elif left in TRIAL_REMINDERS:
            notify(db, f"trial_{left}", subscription, moment)
    if (
        subscription.status == "past_due"
        and subscription.past_due_since
        and moment >= subscription.past_due_since + timedelta(days=GRACE_DAYS)
    ):
        subscription.read_only_since = moment
        move("read_only", "read_only")
    if (
        subscription.status in ("read_only", "canceled")
        and subscription.read_only_since
        and moment >= subscription.read_only_since + timedelta(days=READ_ONLY_DAYS)
    ):
        move("suspended", "suspended")
        institution = db.get(Institution, institution_id)
        institution.status = "suspended"
        institution.status_reason = BILLING_SUSPENSION
        institution.status_changed_at = moment
    return changes


def lift_billing_suspension(db: Session, institution_id: int) -> None:
    """A payment (or a plan assigned by the platform) ends an automatic suspension."""
    institution = db.get(Institution, institution_id)
    if (
        institution is not None
        and institution.status == "suspended"
        and institution.status_reason == BILLING_SUSPENSION
    ):
        institution.status = "active"
        institution.status_reason = "Reactivada por pago"
        institution.status_changed_at = now()


NOTICES = {
    "trial_7": (
        "Tu prueba de Nexo termina en 7 días",
        "Tu prueba gratuita termina el {trial_end}. Elige un plan para seguir sin interrupciones.",
    ),
    "trial_3": (
        "Tu prueba de Nexo termina en 3 días",
        "Tu prueba gratuita termina el {trial_end}. Elige un plan para seguir sin interrupciones.",
    ),
    "trial_1": (
        "Tu prueba de Nexo termina mañana",
        "Tu prueba gratuita termina mañana. Elige un plan para seguir sin interrupciones.",
    ),
    "trial_ended": (
        "Terminó tu prueba de Nexo",
        "La prueba gratuita terminó. Tienes {grace} días para elegir un plan con acceso "
        "completo; después la institución pasará a modo de solo lectura.",
    ),
    "past_due": (
        "No pudimos cobrar tu plan de Nexo",
        "El último pago no se pudo completar. Tienes {grace} días para actualizar el método de "
        "pago; después la institución pasará a modo de solo lectura.",
    ),
    "read_only": (
        "Tu institución está en modo de solo lectura",
        "Por falta de pago, Nexo está en modo de solo lectura: se puede consultar y exportar, "
        "pero no registrar cambios. Si no se regulariza en {read_only} días, el acceso se "
        "suspenderá. Tus datos se conservan.",
    ),
    "suspended": (
        "El acceso a Nexo está suspendido",
        "Por falta de pago, el acceso de la institución está suspendido. Tus datos se "
        "conservan: regulariza el pago o escribe al equipo de Nexo para reactivarla.",
    ),
}


def notify(db: Session, notice: str, subscription: Subscription, moment: datetime) -> int:
    """Email the institution's billing managers once per notice and date."""
    from app.auth import has_permission
    from app.models.user_model import User
    from app.services.email_service import queue_email
    from app.services.email_templates import optional_link, render

    subject, text = NOTICES[notice]
    body = text.format(
        trial_end=subscription.trial_ends_at.strftime("%d/%m/%Y")
        if subscription.trial_ends_at
        else "",
        grace=GRACE_DAYS,
        read_only=READ_ONLY_DAYS,
    )
    sent = 0
    for user in db.query(User).filter(User.active.is_(True)).order_by(User.user_id):
        if not user.email or not has_permission(user, "billing.manage"):
            continue
        message = render(
            db,
            subject,
            f"Hola, {user.username}:",
            [body],
            action=optional_link("Abrir Plan y facturación", "/billing"),
        )
        queued = queue_email(
            db,
            user.email,
            message.subject,
            message.text,
            message.html,
            category="billing",
            user_id=user.user_id,
            dedupe_key=f"billing:{subscription.institution_id}:{notice}:{moment.date()}:{user.user_id}",
        )
        sent += queued is not None
    return sent
