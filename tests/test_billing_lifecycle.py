"""Trial, grace, read-only mode and suspension of unpaid subscriptions (Fase 4 D3)."""

from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException
from route_analysis import reaches, write_routes
from test_billing import ORIGIN, set_subscription, start_checkout, subscription
from test_plans import new_student
from test_write_audit import demo  # noqa: F401  (shared fixture)

from app.db.tenant import set_tenant
from app.models import EmailOutbox, Institution, PlatformAuditLog
from app.services.billing import access
from app.services.billing.lifecycle import BILLING_SUSPENSION, advance
from app.services.write_locks import lock_academic, lock_scope

NOW = datetime(2026, 12, 1, 12, 0)


def run(sessions, moment):
    with sessions() as db:
        set_tenant(db, 1)
        changes = advance(db, moment)
        db.commit()
    return changes


def billing_emails(sessions) -> list[str]:
    with sessions() as db:
        return [row.subject for row in db.query(EmailOutbox).filter_by(category="billing")]


def test_read_only_blocks_writes_but_not_reading_exporting_or_paying(demo):  # noqa: F811
    client, sessions, tokens = demo
    set_subscription(sessions, plan="basico", status="read_only", read_only_since=NOW)
    blocked = new_student(client, tokens["admin"], sessions)
    assert blocked.status_code == 403 and "solo lectura" in blocked.json()["detail"]
    students = client.get("/students/", headers=tokens["admin"])
    assert students.status_code == 200
    student = students.json()[0]["student_id"]
    edit = client.patch(f"/students/{student}", headers=tokens["admin"], json={"telephone": "1"})
    assert edit.status_code == 403
    assert client.get("/bulk/students/export", headers=tokens["admin"]).status_code == 200
    status = client.get("/billing/status", headers=tokens["docente"]).json()
    assert status["read_only"] is True and status["status"] == "read_only"
    # Paying is allowed, and it gives the institution its writes back.
    token = start_checkout(client, tokens["admin"])
    paid = client.post(
        "/billing/sandbox/complete",
        headers=tokens["admin"],
        json={"token": token, "outcome": "paid"},
    )
    assert paid.status_code == 200 and paid.json()["status"] == "active"
    assert new_student(client, tokens["admin"], sessions).status_code == 200


def test_locks_refuse_only_signed_in_requests(demo):  # noqa: F811
    _client, sessions, _tokens = demo
    set_subscription(sessions, status="read_only", read_only_since=NOW)
    with sessions() as db:
        set_tenant(db, 1)
        lock_scope(db, "finance")  # scheduled jobs and scripts are never blocked
        db.rollback()
    with sessions() as db:
        set_tenant(db, 1)
        access.enforce_plan(db)
        with pytest.raises(HTTPException) as refused:
            lock_academic(db, sections=[1])
        assert refused.value.status_code == 403
        db.rollback()


def test_trial_reminders_then_grace_then_read_only_then_suspension(demo):  # noqa: F811
    client, sessions, tokens = demo
    set_subscription(
        sessions, plan="basico", status="trialing", trial_ends_at=NOW + timedelta(days=7)
    )
    assert run(sessions, NOW) == []
    assert run(sessions, NOW) == []  # same day: the reminder is not repeated
    reminders = billing_emails(sessions)
    assert len(reminders) == 1 and "termina en 7 días" in reminders[0]
    assert run(sessions, NOW + timedelta(days=5)) == []  # 2 days left: no reminder that day
    ended = NOW + timedelta(days=7, hours=1)
    assert run(sessions, ended) == ["trialing → past_due"]
    # Grace: full access for 7 days.
    assert new_student(client, tokens["admin"], sessions, "gracia@ejemplo.do").status_code == 200
    assert run(sessions, ended + timedelta(days=6)) == []
    assert run(sessions, ended + timedelta(days=7)) == ["past_due → read_only"]
    assert new_student(client, tokens["admin"], sessions, "bloqueo@ejemplo.do").status_code == 403
    assert run(sessions, ended + timedelta(days=36)) == []
    assert run(sessions, ended + timedelta(days=37)) == ["read_only → suspended"]
    with sessions() as db:
        institution = db.get(Institution, 1)
        assert institution.status == "suspended" and institution.status_reason == BILLING_SUSPENSION
        actions = [row.action for row in db.query(PlatformAuditLog)]
    assert {"billing.past_due", "billing.read_only", "billing.suspended"} <= set(actions)
    subjects = " | ".join(billing_emails(sessions))
    assert (
        "Terminó tu prueba" in subjects and "solo lectura" in subjects and "suspendido" in subjects
    )
    login = client.post(
        "/auth/login",
        json={"username": "demo.admin", "password": "NexoAdmin2026!", "institution": "principal"},
    )
    assert login.status_code == 403


def test_a_payment_lifts_an_automatic_suspension(demo):  # noqa: F811
    client, sessions, tokens = demo
    token = start_checkout(client, tokens["admin"])
    set_subscription(sessions, status="suspended", read_only_since=NOW)
    with sessions() as db:
        institution = db.get(Institution, 1)
        institution.status, institution.status_reason = "suspended", BILLING_SUSPENSION
        db.commit()
    from app.services.billing import lifecycle
    from app.services.billing.providers import SandboxProvider

    with sessions() as db:
        set_tenant(db, 1)
        for event in SandboxProvider().complete(token, "paid"):
            lifecycle.apply(db, "sandbox", event)
        db.commit()
    with sessions() as db:
        assert db.get(Institution, 1).status == "active"
    assert subscription(sessions).status == "active"
    assert client.get("/students/", headers=tokens["admin"]).status_code == 200


def test_a_manual_suspension_is_not_lifted_by_payments(demo):  # noqa: F811
    _client, sessions, _tokens = demo
    from app.services.billing.lifecycle import lift_billing_suspension

    with sessions() as db:
        institution = db.get(Institution, 1)
        institution.status, institution.status_reason = "suspended", "Uso indebido"
        db.commit()
        lift_billing_suspension(db, 1)
        db.commit()
        assert db.get(Institution, 1).status == "suspended"


def test_a_failed_payment_emails_the_billing_managers(demo):  # noqa: F811
    client, sessions, tokens = demo
    set_subscription(sessions, plan="basico", status="active")
    token = start_checkout(client, tokens["admin"])
    client.post(
        "/billing/sandbox/complete",
        headers={**tokens["admin"], **ORIGIN},
        json={"token": token, "outcome": "failed"},
    )
    assert any("No pudimos cobrar" in subject for subject in billing_emails(sessions))


# Writes a read-only institution may still do (paying): reviewed one by one.
READ_ONLY_EXEMPT = {
    ("POST", "/billing/checkout"),
    ("POST", "/billing/portal"),
    ("POST", "/billing/sandbox/complete"),
    ("POST", "/legal/accept"),  # new terms can be accepted while unpaid
    ("POST", "/support/tickets"),  # an unpaid institution can still ask for help
    ("POST", "/support/tickets/{ticket_id}/messages"),
}


def test_only_reviewed_routes_skip_the_read_only_mode():
    exempt = {
        (method, path)
        for method, path, route in write_routes()
        if reaches(route.endpoint, {access.allow_while_read_only})
    }
    assert exempt == READ_ONLY_EXEMPT
