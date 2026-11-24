"""Scheduled jobs worker (Fase 4 C)."""

from datetime import UTC, datetime, time, timedelta

import pytest
from db_support import TEST_DATABASE_URL
from sqlalchemy import create_engine

from app.services import scheduler
from app.services.scheduler import Job, acquire_leadership, due, run_due, still_leader

# 2026-11-25 10:00 UTC = 06:00 in Santo Domingo (UTC-4).
BEFORE_BILLING = datetime(2026, 11, 25, 10, 0, tzinfo=UTC)
JOBS = (
    Job("emails", lambda _engine: "ok", every=timedelta(minutes=2)),
    Job("billing", lambda _engine: "ok", at=time(6, 30)),
)


def names(jobs):
    return [job.name for job in jobs]


def test_interval_and_daily_jobs_run_at_their_time():
    last: dict[str, datetime] = {}
    assert names(due(JOBS, last, BEFORE_BILLING)) == ["emails"]
    last["emails"] = BEFORE_BILLING
    assert due(JOBS, last, BEFORE_BILLING + timedelta(minutes=1)) == []
    at_billing = BEFORE_BILLING + timedelta(minutes=30)  # 06:30 local
    assert names(due(JOBS, last, at_billing)) == ["emails", "billing"]
    last.update(emails=at_billing, billing=at_billing)
    # Once a day: later the same day, only the emails again.
    assert names(due(JOBS, last, at_billing + timedelta(hours=5))) == ["emails"]
    # The next business day (00:30 UTC is still the same local day: 20:30).
    assert "billing" not in names(due(JOBS, last, datetime(2026, 11, 26, 0, 30, tzinfo=UTC)))
    assert "billing" in names(due(JOBS, last, datetime(2026, 11, 26, 11, 0, tzinfo=UTC)))


def test_a_failing_job_never_stops_the_others():
    ran = []

    def broken(_engine):
        raise RuntimeError("sin conexión SMTP")

    jobs = (
        Job("emails", broken, every=timedelta(minutes=2)),
        Job("billing", lambda _engine: ran.append("billing") or "ok", at=time(6, 30)),
    )
    last: dict[str, datetime] = {}
    run_due(None, last, BEFORE_BILLING + timedelta(hours=1), jobs)
    assert ran == ["billing"]
    # The failed job waits for its next turn instead of retrying in a loop.
    assert set(last) == {"emails", "billing"}


def test_real_jobs_run_on_an_empty_installation(tmp_path):
    import app.models  # noqa: F401  (every table)
    from app.db.database import Base

    engine = create_engine(f"sqlite:///{tmp_path / 'jobs.db'}")
    Base.metadata.create_all(engine)
    for job in scheduler.JOBS:
        assert isinstance(job.run(engine), str)


@pytest.mark.skipif(TEST_DATABASE_URL is None, reason="Requiere PostgreSQL (advisory locks)")
def test_only_one_scheduler_leads_with_postgresql():
    first_engine, second_engine = create_engine(TEST_DATABASE_URL), create_engine(TEST_DATABASE_URL)
    leader = acquire_leadership(first_engine)
    try:
        assert leader is not None and still_leader(leader)
        assert acquire_leadership(second_engine) is None  # stand-by
    finally:
        leader.close()
    successor = acquire_leadership(second_engine)
    assert successor is not None  # takes over once the first one stops
    successor.close()
    first_engine.dispose()
    second_engine.dispose()
