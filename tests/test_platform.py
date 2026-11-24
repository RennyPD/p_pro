"""Subdomains, platform super administration and onboarding (Fase 4, block B)."""

import pytest
from test_auth_hardening import current_code
from test_multi_tenant import SECOND_PASSWORD, second_institution
from test_write_audit import demo, entries  # noqa: F401  (shared fixtures)

from app.db import database
from app.db.tenant import set_tenant
from app.models import (
    CompetencyGroup,
    EmailOutbox,
    FinancePolicy,
    GradingScale,
    Institution,
    InstitutionSettings,
    PlatformAuditLog,
    Role,
    User,
)
from app.security import create_totp_secret
from app.services.platform import create_admin

PLATFORM_PASSWORD = "PlataformaNexo2026!"


@pytest.fixture
def domain(monkeypatch):
    monkeypatch.setattr(database.settings, "tenant_base_domain", "nexo.test")
    return "nexo.test"


def host(code):
    return {"host": f"{code}.nexo.test"}


def test_the_subdomain_names_the_institution_and_tokens_stay_home(demo, domain):  # noqa: F811
    client, sessions, tokens = demo
    second_institution(sessions)
    # Same username in two institutions: the address decides, no code needed.
    login = client.post(
        "/auth/login",
        headers=host("segundo"),
        json={"username": "demo.admin", "password": SECOND_PASSWORD},
    )
    assert login.status_code == 200, login.text
    second = {"Authorization": "Bearer " + login.json()["access_token"], **host("segundo")}
    assert client.get("/auth/me", headers=second).status_code == 200
    # The first institution's token is refused at the second institution's address.
    foreign = {**tokens["admin"], **host("segundo")}
    response = client.get("/students/", headers=foreign)
    assert response.status_code == 401 and "otra institución" in response.json()["detail"]
    # Unknown hosts are not trusted: the code fallback still works.
    assert (
        client.get("/auth/me", headers={**tokens["admin"], "host": "evil.example"}).status_code
        == 200
    )
    # API on its own host: the page's origin names the institution.
    origin = {"host": "api.nexo.test", "origin": "https://segundo.nexo.test"}
    assert client.get("/students/", headers={**tokens["admin"], **origin}).status_code == 401
    assert client.get("/public/institution", headers=origin).json()["code"] == "segundo"
    public = client.get("/public/institution", headers=host("segundo")).json()
    assert public == {"code": "segundo", "name": "Colegio Segundo", "status": "active"}
    assert client.get("/public/institution?code=principal").json()["code"] == "principal"
    assert client.get("/public/institution", headers=host("nadie")).status_code == 404


def platform_admin(sessions):
    secret = create_totp_secret()
    with sessions() as db:
        create_admin(db, "soporte@nexo.com.do", "Equipo Nexo", PLATFORM_PASSWORD, secret)
        db.commit()
    return secret


def platform_login(client, secret, code=None):
    response = client.post(
        "/platform/auth/login",
        json={
            "email": "soporte@nexo.com.do",
            "password": PLATFORM_PASSWORD,
            "otp": code or current_code(secret),
        },
    )
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def test_platform_accounts_require_the_second_factor_and_never_mix(demo):  # noqa: F811
    client, sessions, tokens = demo
    secret = platform_admin(sessions)
    wrong = client.post(
        "/platform/auth/login",
        json={"email": "soporte@nexo.com.do", "password": PLATFORM_PASSWORD, "otp": "000000"},
    )
    assert wrong.status_code == 401
    code = current_code(secret)
    platform = platform_login(client, secret, code)
    # The same code cannot be replayed (even if the clock moved to the next step).
    replay = client.post(
        "/platform/auth/login",
        json={"email": "soporte@nexo.com.do", "password": PLATFORM_PASSWORD, "otp": code},
    )
    assert replay.status_code == 401
    assert client.get("/platform/me", headers=platform).json()["email"] == "soporte@nexo.com.do"
    # A platform token never opens institution data, and the reverse.
    assert client.get("/students/", headers=platform).status_code == 401
    assert client.get("/platform/institutions", headers=tokens["admin"]).status_code == 403
    with sessions() as db:
        actions = [row.action for row in db.query(PlatformAuditLog)]
    assert "platform.login_failed" in actions and "platform.login" in actions


def test_creating_an_institution_prepares_it_and_invites_its_admin(demo, monkeypatch):  # noqa: F811
    client, sessions, _tokens = demo
    monkeypatch.setattr(database.settings, "app_url", "https://nexo.example.edu")
    platform = platform_login(client, platform_admin(sessions))
    body = {
        "name": "Liceo Horizonte",
        "code": "liceo-horizonte",
        "institution_type": "school",
        "admin_email": "direccion@horizonte.edu.do",
    }
    reserved = client.post(
        "/platform/institutions", headers=platform, json={**body, "code": "admin"}
    )
    assert reserved.status_code == 422
    created = client.post("/platform/institutions", headers=platform, json=body)
    assert created.status_code == 200, created.text
    data = created.json()
    assert data["code"] == "liceo-horizonte" and data["usage"]["users"] == 1
    duplicate = client.post("/platform/institutions", headers=platform, json=body)
    assert duplicate.status_code == 409
    institution_id = data["institution_id"]
    with sessions() as db:
        set_tenant(db, institution_id)
        settings = db.query(InstitutionSettings).one()
        assert settings.institution_type == "school" and settings.students_view_finance is False
        assert {r.name for r in db.query(Role)} == {"admin", "teacher", "student", "guardian"}
        assert db.query(GradingScale).filter_by(is_default=True).count() == 1
        assert db.query(FinancePolicy).one().late_fee_enabled is False
        assert db.query(CompetencyGroup).count() == 4
        admin = db.query(User).one()
        assert admin.email == "direccion@horizonte.edu.do"
        invite = db.query(EmailOutbox).filter_by(to_address="direccion@horizonte.edu.do").one()
        assert "Activa tu cuenta" in invite.subject
    listed = client.get("/platform/institutions?q=horizonte", headers=platform)
    assert listed.headers["X-Total-Count"] == "1"
    assert entries(sessions, "institution.created", f"institution:{institution_id}")


def test_suspension_blocks_access_with_a_message(demo):  # noqa: F811
    client, sessions, tokens = demo
    platform = platform_login(client, platform_admin(sessions))
    suspended = client.post(
        "/platform/institutions/1/suspend", headers=platform, json={"reason": "Pago pendiente"}
    )
    assert suspended.status_code == 200, suspended.text
    assert suspended.json()["status"] == "suspended"
    blocked = client.get("/students/", headers=tokens["admin"])
    assert blocked.status_code == 403 and "suspendida" in blocked.json()["detail"]
    sign_in = client.post(
        "/auth/login",
        json={"username": "demo.admin", "password": "NexoAdmin2026!", "institution": "principal"},
    )
    assert sign_in.status_code == 403 and "suspendida" in sign_in.json()["detail"]
    again = client.post(
        "/platform/institutions/1/suspend", headers=platform, json={"reason": "Otra vez"}
    )
    assert again.status_code == 409
    reactivated = client.post(
        "/platform/institutions/1/reactivate", headers=platform, json={"reason": "Pago recibido"}
    )
    assert reactivated.status_code == 200
    assert client.get("/students/", headers=tokens["admin"]).status_code == 200
    audit = client.get("/platform/audit", headers=platform).json()
    assert [row["action"] for row in audit[:2]] == [
        "institution.reactivated",
        "institution.suspended",
    ]
    with sessions() as db:
        assert db.get(Institution, 1).status_reason == "Pago recibido"


def test_first_steps_checklist(demo):  # noqa: F811
    client, _sessions, tokens = demo
    checklist = client.get("/onboarding/checklist", headers=tokens["admin"])
    assert checklist.status_code == 200, checklist.text
    body = checklist.json()
    steps = {step["key"]: step for step in body["steps"]}
    assert steps["students"]["done"] and steps["teachers"]["done"] and steps["programs"]["done"]
    assert steps["students"]["to"] == "/students"
    assert body["completed"] <= body["total"]
    assert client.get("/onboarding/checklist", headers=tokens["docente"]).status_code == 403
