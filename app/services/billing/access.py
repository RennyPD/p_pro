"""Read-only mode for unpaid subscriptions (Fase 4, block D3).

Every write route takes a domain lock (``tests/test_route_locks.py``), so the
check lives in the locks: a read-only institution can sign in, read and
export, but no write gets past ``lock_scope`` / ``lock_academic``.

It applies to requests of signed-in institution accounts only (``get_current_user``
marks the session). Platform routes, scheduled jobs and scripts are never
blocked, and a few routes are explicitly allowed (paying, managing the
payment method) with ``allow_while_read_only``. The sign-in and the account's
own security (password, second factor) use the per-account lock and stay
available.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.tenant import current_tenant

ENFORCE = "nexo_plan_enforced"
EXEMPT = "nexo_read_only_exempt"
BLOCKED_STATUSES = frozenset({"read_only", "suspended", "canceled"})
READ_ONLY_MESSAGE = (
    "La institución está en modo de solo lectura por falta de pago. Puedes consultar y "
    "exportar; para volver a registrar cambios, regulariza el pago en «Plan y facturación»"
)


def enforce_plan(db: Session) -> None:
    """Called by the authentication of institution accounts."""
    db.info[ENFORCE] = True


def allow_while_read_only(db: Session) -> None:
    """For the few writes a read-only institution needs (paying)."""
    db.info[EXEMPT] = True


def ensure_writable(db: Session) -> None:
    if not db.info.get(ENFORCE) or db.info.get(EXEMPT):
        return
    institution_id = current_tenant(db)
    if institution_id is None:
        return
    from app.models.billing_model import Subscription

    status = (
        db.query(Subscription.status).filter(Subscription.institution_id == institution_id).scalar()
    )
    if status in BLOCKED_STATUSES:
        raise HTTPException(403, READ_ONLY_MESSAGE)
