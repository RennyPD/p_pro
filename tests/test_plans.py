"""SaaS plans, subscriptions and limits (Fase 4, block D1)."""

from datetime import datetime, timedelta

import pytest
from test_object_storage import PDF, upload
from test_platform import platform_admin, platform_login
from test_write_audit import demo  # noqa: F401  (shared fixture)

from app.models import Career, PlatformAuditLog, Role, Student, Subscription
from app.services.billing import limits
from app.services.billing.limits import ceiling

PLAN = {
    "code": "mini",
    "name": "Mini",
    "description": "Prueba",
    "currency": "USD",
    "monthly_price": "10.00",
    "yearly_price": "100.00",
    "max_students": 1,
    "max_staff": 1,
    "storage_gb": 1,
}


def new_student(client, token, sessions, email="nuevo@ejemplo.do"):
    with sessions() as db:
        career = db.query(Career).first().career_id
    return client.post(
        "/students/",
        headers=token,
        json={
            "first_name": "Nuevo",
            "last_name": "Estudiante",
            "email": email,
            "telephone": "809",
            "address": "SD",
            "career_id": career,
        },
    )


@pytest.fixture
def platform(demo):  # noqa: F811
    client, sessions, tokens = demo
    headers = platform_login(client, platform_admin(sessions))
    return client, sessions, tokens, headers


def assign(client, headers, code, institution_id=1, **extra):
    return client.put(
        f"/platform/institutions/{institution_id}/subscription",
        headers=headers,
        json={"plan_code": code, "reason": "Acuerdo comercial de prueba", **extra},
    )


def test_existing_institutions_keep_an_unlimited_active_plan(platform):
    client, sessions, tokens, headers = platform
    listed = client.get("/platform/institutions?q=principal", headers=headers).json()[0]
    assert listed["subscription"]["plan_code"] == "institucional"
    assert listed["subscription"]["status"] == "active"
    assert listed["usage"]["staff"] >= 1
    assert new_student(client, tokens["admin"], sessions).status_code == 200


def test_new_institutions_start_a_trial(platform, monkeypatch):
    client, sessions, _tokens, headers = platform
    from app.db.database import settings

    monkeypatch.setattr(settings, "app_url", "https://nexo.example.edu")
    created = client.post(
        "/platform/institutions",
        headers=headers,
        json={
            "name": "Colegio Prueba",
            "code": "colegio-prueba",
            "institution_type": "school",
            "admin_email": "direccion@prueba.edu.do",
        },
    )
    assert created.status_code == 200, created.text
    subscription = created.json()["subscription"]
    assert subscription["plan_code"] == "profesional" and subscription["status"] == "trialing"
    ends = datetime.fromisoformat(subscription["trial_ends_at"])
    assert timedelta(days=29) < ends - datetime.now() < timedelta(days=31)
    unknown = client.post(
        "/platform/institutions",
        headers=headers,
        json={
            "name": "Otro",
            "code": "otro-colegio",
            "institution_type": "school",
            "admin_email": "a@otro.edu.do",
            "plan_code": "no-existe",
        },
    )
    assert unknown.status_code == 404


def test_plans_are_managed_and_audited_by_the_platform(platform):
    client, sessions, tokens, headers = platform
    assert [p["code"] for p in client.get("/platform/plans", headers=headers).json()] == [
        "basico",
        "profesional",
        "institucional",
    ]
    created = client.post("/platform/plans", headers=headers, json=PLAN)
    assert created.status_code == 200, created.text
    assert client.post("/platform/plans", headers=headers, json=PLAN).status_code == 409
    edited = client.put(
        "/platform/plans/mini",
        headers=headers,
        json={**{k: v for k, v in PLAN.items() if k != "code"}, "monthly_price": "12.50"},
    )
    assert edited.json()["monthly_price"] == "12.50"
    # Only the platform: an institution token is refused.
    assert client.get("/platform/plans", headers=tokens["admin"]).status_code == 403
    with sessions() as db:
        actions = {row.action for row in db.query(PlatformAuditLog)}
    assert {"plan.created", "plan.updated"} <= actions


def test_limits_refuse_additions_but_never_touch_what_exists(platform, monkeypatch):
    client, sessions, tokens, headers = platform
    client.post("/platform/plans", headers=headers, json=PLAN)
    changed = assign(client, headers, "mini")
    assert changed.status_code == 200 and changed.json()["subscription"]["plan_code"] == "mini"

    refused = new_student(client, tokens["admin"], sessions)
    assert refused.status_code == 409
    assert "Tu plan Mini permite 1 estudiantes activos" in refused.json()["detail"]
    assert "Plan y facturación" in refused.json()["detail"]
    # Existing students are still listed and editable.
    students = client.get("/students/", headers=tokens["admin"])
    assert students.status_code == 200 and len(students.json()) >= 1
    student = students.json()[0]["student_id"]
    assert (
        client.patch(
            f"/students/{student}", headers=tokens["admin"], json={"telephone": "8095550000"}
        ).status_code
        == 200
    )
    # Reactivating a student counts like a new one: free the seat, fill it, reactivate.
    client.patch(f"/students/{student}", headers=tokens["admin"], json={"active": False})
    assert new_student(client, tokens["admin"], sessions, "cupo@ejemplo.do").status_code == 200
    reactivate = client.patch(
        f"/students/{student}", headers=tokens["admin"], json={"active": True}
    )
    assert reactivate.status_code == 409

    # Staff accounts are limited; student accounts are not.
    with sessions() as db:
        roles = {role.name: role.role_id for role in db.query(Role).filter_by(institution_id=1)}
    staff = client.post(
        "/users/",
        headers=tokens["admin"],
        json={
            "username": "nuevo.docente",
            "email": "docente@ejemplo.do",
            "password": "NuevoDocente2026!",
            "role_id": roles["teacher"],
        },
    )
    assert staff.status_code == 409 and "cuentas del personal" in staff.json()["detail"]

    # Files: 1 "GB" made tiny for the test.
    monkeypatch.setattr(limits, "GB", 10)
    full = upload(client, tokens["admin"], student, PDF)
    assert full.status_code == 409 and "GB de archivos" in full.json()["detail"]

    # Back to an unlimited plan: everything is allowed again.
    assign(client, headers, "institucional")
    assert new_student(client, tokens["admin"], sessions, "otro@ejemplo.do").status_code == 200


def test_the_margin_is_ten_percent():
    assert ceiling(100) == 110 and ceiling(300) == 330 and ceiling(1) == 1


def test_a_trial_can_be_granted_by_the_platform(platform):
    client, sessions, _tokens, headers = platform
    granted = assign(client, headers, "basico", trial_days=14)
    assert granted.json()["subscription"]["status"] == "trialing"
    with sessions() as db:
        row = db.query(Subscription).filter_by(institution_id=1).one()
        assert row.plan.code == "basico" and row.trial_ends_at > datetime.now()
        active_students = db.query(Student).filter_by(institution_id=1, active=True).count()
    assert active_students > 0
