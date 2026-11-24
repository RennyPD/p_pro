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
    subscription.status = "active"
    subscription.past_due_since = None
    subscription.read_only_since = None
    subscription.canceled_at = None
    subscription.trial_ends_at = None
    if event.period_end:
        subscription.current_period_end = event.period_end
