"""Scheduled jobs in one worker process (Fase 4 C).

Replaces external cron entries. ``python -m scripts.scheduler`` runs:
- ``emails`` every 2 minutes: pending and retried emails.
- ``billing`` daily from 06:30 (America/Santo_Domingo): plans, discounts, late
  fees and holds per institution, then old request-limit windows are purged.
- ``reminders`` daily from 07:00: due-date reminders per institution.

Every job is idempotent (running it twice, or after a missed day, changes
nothing twice), so a restart after the hour simply runs it again. With
PostgreSQL, a session-level advisory lock keeps a single active scheduler
even if several worker replicas start; the others wait as stand-by.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, time, timedelta

from sqlalchemy import Engine, text

from app.services.business_time import INSTITUTION_TIME_ZONE

logger = logging.getLogger("nexo.scheduler")
ADVISORY_LOCK = 734_221_001  # "nexo scheduler"


@dataclass(frozen=True)
class Job:
    name: str
    run: Callable[[Engine], str]
    every: timedelta | None = None  # interval jobs
    at: time | None = None  # daily jobs, business time


def send_emails(engine: Engine) -> str:
    from app.services.email_service import deliver_pending

    total = {"sent": 0, "failed": 0}
    while True:
        result = deliver_pending(engine)
        total = {key: total[key] + result[key] for key in total}
        if result["sent"] + result["failed"] == 0:
            break
    return f"Correos enviados: {total['sent']}; fallidos definitivamente: {total['failed']}"


def run_billing(engine: Engine) -> str:
    from app.services.finance_automation import run_daily
    from app.services.rate_limit import purge
    from app.services.tenants import for_each_institution

    results = for_each_institution(engine, run_daily, commit=True)
    purge(engine)
    charges = sum(len(result.billing_runs) for result in results.values())
    return f"Cobros diarios en {len(results)} instituciones; {charges} generaciones"


def send_reminders(engine: Engine) -> str:
    from app.services.email_notices import queue_due_reminders
    from app.services.email_service import deliver_pending
    from app.services.tenants import for_each_institution

    queued = sum(for_each_institution(engine, queue_due_reminders).values())
    sent = deliver_pending(engine)
    return f"Recordatorios en cola: {queued}; enviados ahora: {sent['sent']}"


def advance_subscriptions(engine: Engine) -> str:
    from sqlalchemy.orm import Session

    from app.services.billing.lifecycle import advance
    from app.services.email_service import deliver_pending
    from app.services.platform import expire_signups
    from app.services.tenants import for_each_institution

    with Session(bind=engine) as db:  # system session: every institution
        expired = expire_signups(db)
        db.commit()
    if expired:
        logger.info("signups_expired", extra={"codes": expired})
    changes = {key: value for key, value in for_each_institution(engine, advance).items() if value}
    deliver_pending(engine)
    return f"Suscripciones: {len(changes)} cambios" + (f" {changes}" if changes else "")


def expire_online_payments(engine: Engine) -> str:
    from app.services.payments.intents import expire_stale
    from app.services.tenants import for_each_institution

    results = {
        k: v for k, v in for_each_institution(engine, expire_stale).items() if any(v.values())
    }
    return (
        f"Pagos en línea vencidos o resueltos: {results}"
        if results
        else "Sin pagos en línea pendientes"
    )


JOBS = (
    Job("emails", send_emails, every=timedelta(minutes=2)),
    Job("online_payments", expire_online_payments, every=timedelta(minutes=10)),
    Job("subscriptions", advance_subscriptions, at=time(6, 0)),
    Job("billing", run_billing, at=time(6, 30)),
    Job("reminders", send_reminders, at=time(7, 0)),
)


def local(moment: datetime) -> datetime:
    """Business time (aware) for an aware or naive-UTC moment."""
    if moment.tzinfo is None:
        from datetime import UTC

        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(INSTITUTION_TIME_ZONE)


def due(jobs, last_runs: dict[str, datetime], moment: datetime) -> list[Job]:
    """Jobs to run at ``moment`` given when each one last ran."""
    now = local(moment)
    ready = []
    for job in jobs:
        last = last_runs.get(job.name)
        if job.every is not None:
            if last is None or now - local(last) >= job.every:
                ready.append(job)
        elif now.time() >= job.at and (last is None or local(last).date() < now.date()):
            ready.append(job)
    return ready


def run_due(engine: Engine, last_runs: dict[str, datetime], moment: datetime, jobs=JOBS):
    """Run what is due; one failing job never stops the others."""
    for job in due(jobs, last_runs, moment):
        try:
            summary = job.run(engine)
            logger.info("job_done", extra={"job": job.name, "summary": summary})
        except Exception:
            logger.exception("job_failed", extra={"job": job.name})
        # Failed jobs wait for their next turn too: no tight retry loop.
        last_runs[job.name] = moment


def acquire_leadership(engine: Engine):
    """Hold the advisory lock on a dedicated connection; None if another holds it."""
    if engine.dialect.name != "postgresql":
        return engine.connect()  # SQLite: development, a single process
    connection = engine.connect()
    # Out of the pool: closing it must really end the database session, which
    # releases the lock (a pooled connection would keep it held forever).
    connection.detach()
    locked = connection.execute(
        text("SELECT pg_try_advisory_lock(:key)"), {"key": ADVISORY_LOCK}
    ).scalar()
    connection.commit()
    if locked:
        return connection
    connection.close()
    return None


def still_leader(connection) -> bool:
    """The lock lives with the connection: if the database dropped it, lead again later."""
    try:
        connection.execute(text("SELECT 1"))
        connection.commit()
        return True
    except Exception:
        logger.warning("scheduler_connection_lost")
        try:
            connection.close()
        except Exception:
            pass
        return False
