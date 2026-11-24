"""Public self sign-up of an institution (Fase 4, block D4)."""

from datetime import datetime, timedelta

import pytest
from test_email import last_email, link_token
from test_write_audit import demo  # noqa: F401  (shared fixture)

from app.db.database import settings
from app.models import Institution, PlatformAuditLog, Subscription
from app.services import rate_limit
from app.services.platform import expire_signups

EMAIL = "direccion@colegio-nuevo.edu.do"
BODY = {
    "name": "Colegio Nuevo Amanecer",
    "code": "colegio-nuevo",
    "institution_type": "school",
    "admin_email": EMAIL,
    "plan_code": "basico",
}


@pytest.fixture
def open_signup(demo, monkeypatch):  # noqa: F811
    monkeypatch.setattr(settings, "app_url", "https://nexo.example.edu")
    monkeypatch.setattr(rate_limit, "now", lambda: datetime(2026, 11, 25, 10, 0))
    return demo


def institution(sessions, code="colegio-nuevo"):
    with sessions() as db:
        row = db.query(Institution).filter_by(slug=code).first()
        if row is not None:
            db.expunge(row)
        return row


def test_the_page_lists_public_plans_and_checks_codes(open_signup):
    client, _sessions, _tokens = open_signup
    config = client.get("/public/signup").json()
    assert config["enabled"] is True and config["trial_days"] == 30
    assert [plan["code"] for plan in config["plans"]] == ["basico", "profesional"]
    assert client.get("/public/signup/code?code=principal").json() == {
        "available": False,
        "reason": "Ese código ya está en uso",
    }
    assert client.get("/public/signup/code?code=admin").json()["available"] is False
    assert client.get("/public/signup/code?code=colegio-nuevo").json()["available"] is True


def test_sign_up_verifies_the_email_before_the_institution_starts(open_signup):
    client, sessions, _tokens = open_signup
    created = client.post("/public/signup", json=BODY)
    assert created.status_code == 202, created.text
    assert "Te enviamos un correo" in created.json()["message"]
    row = institution(sessions)
    assert row.status == "pending" and row.contact_email == EMAIL
    pending = client.post(
        "/auth/login",
        json={"username": EMAIL, "password": "x" * 12, "institution": "colegio-nuevo"},
    )
    assert pending.status_code == 403 and "aún no está activada" in pending.json()["detail"]

    subject, body, _status, _category = last_email(sessions, EMAIL)
    assert "Activa tu cuenta" in subject
    activated = client.post(
        "/auth/password-reset/confirm",
        json={"token": link_token(body), "new_password": "ColegioNuevo2026!"},
    )
    assert activated.status_code == 204, activated.text
    row = institution(sessions)
    assert row.status == "active"
    with sessions() as db:
        trial = db.query(Subscription).filter_by(institution_id=row.institution_id).one()
        assert trial.status == "trialing" and trial.plan.code == "basico"
        assert timedelta(days=29) < trial.trial_ends_at - datetime.now() < timedelta(days=31)
        actions = {item.action for item in db.query(PlatformAuditLog)}
    assert {"institution.created", "institution.activated"} <= actions
    login = client.post(
        "/auth/login",
        json={"username": EMAIL, "password": "ColegioNuevo2026!", "institution": "colegio-nuevo"},
    )
    assert login.status_code == 200, login.text


def test_bots_custom_plans_taken_and_reserved_codes_are_refused(open_signup):
    client, sessions, _tokens = open_signup
    bot = client.post("/public/signup", json={**BODY, "website": "https://spam.example"})
    assert bot.status_code == 202 and institution(sessions) is None  # nothing created
    custom = client.post("/public/signup", json={**BODY, "plan_code": "institucional"})
    assert custom.status_code == 422
    assert client.post("/public/signup", json={**BODY, "code": "principal"}).status_code == 409
    assert client.post("/public/signup", json={**BODY, "code": "admin"}).status_code == 422


def test_sign_up_can_be_closed_and_is_rate_limited(open_signup, monkeypatch):
    client, _sessions, _tokens = open_signup
    codes = [
        client.post("/public/signup", json={**BODY, "code": f"colegio-{index}"}).status_code
        for index in range(rate_limit.SIGNUP.hits + 1)
    ]
    assert codes[:-1] == [202] * rate_limit.SIGNUP.hits and codes[-1] == 429
    monkeypatch.setattr(settings, "signup_enabled", False)
    monkeypatch.setattr(rate_limit, "now", lambda: datetime(2026, 11, 25, 12, 0))
    closed = client.post("/public/signup", json={**BODY, "code": "otro-colegio"})
    assert closed.status_code == 403
    assert client.get("/public/signup").json()["enabled"] is False


def test_unverified_sign_ups_free_their_code_after_a_week(open_signup):
    client, sessions, _tokens = open_signup
    client.post("/public/signup", json=BODY)
    with sessions() as db:
        assert expire_signups(db, datetime.now() + timedelta(days=6)) == []
        assert expire_signups(db, datetime.now() + timedelta(days=8)) == ["colegio-nuevo"]
        db.commit()
    assert institution(sessions) is None
    assert client.get("/public/signup/code?code=colegio-nuevo").json()["available"] is True
    again = client.post("/public/signup", json=BODY)
    assert again.status_code == 202 and institution(sessions).status == "pending"
