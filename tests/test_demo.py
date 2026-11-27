"""Public demo institution (Fase 5, step G2)."""

import pytest
from test_billing import ORIGIN
from test_write_audit import demo as installation  # noqa: F401  (shared fixture)

from app.db.database import settings
from app.db.tenant import set_tenant
from app.models import Institution, Permission, Student, User
from app.services.demo import DEMO_CODE, reset_demo
from app.services.email_service import queue_email


@pytest.fixture
def demo_site(installation, monkeypatch):  # noqa: F811
    client, sessions, tokens = installation
    monkeypatch.setattr(settings, "demo_enabled", True)
    engine = sessions.kw["bind"]
    from app.services.permission_catalog import sync_permission_catalog

    with sessions() as db:
        sync_permission_catalog(db)  # the shared catalog exists before the demo
        db.commit()
        own_students = db.query(Student).filter_by(institution_id=1).count()
        permissions = db.query(Permission).count()
    assert permissions > 30
    reset_demo(engine)
    return client, sessions, tokens, engine, own_students, permissions


def demo_id(sessions) -> int:
    with sessions() as db:
        return db.query(Institution).filter_by(slug=DEMO_CODE).one().institution_id


def enter(client, role):
    response = client.post("/public/demo/login", json={"role": role})
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def test_the_demo_is_restored_without_touching_other_institutions(demo_site):
    client, sessions, tokens, engine, own_students, permissions = demo_site
    institution = demo_id(sessions)
    with sessions() as db:
        assert db.query(Student).filter_by(institution_id=1).count() == own_students
        assert db.query(Permission).count() == permissions  # the shared catalog is intact
        demo_students = db.query(Student).filter_by(institution_id=institution).count()
        assert demo_students > 10
    reset_demo(engine)  # nightly: same data again, never duplicated
    with sessions() as db:
        assert db.query(Student).filter_by(institution_id=institution).count() == demo_students
        assert (
            db.query(User).filter_by(institution_id=institution, username="admin.horizonte").count()
            == 1
        )
    assert client.get("/students/", headers=tokens["admin"]).status_code == 200


def test_one_click_entry_for_every_role(demo_site):
    client, sessions, _tokens, _engine, _own, _permissions = demo_site
    info = client.get("/public/demo").json()
    assert info["enabled"] is True
    assert [item["role"] for item in info["roles"]] == ["admin", "teacher", "student", "guardian"]
    institution = demo_id(sessions)
    for role, username in (
        ("admin", "admin.horizonte"),
        ("teacher", "profesor.01"),
        ("student", "estudiante.001"),
        ("guardian", "tutor.01"),
    ):
        me = client.get("/auth/me", headers=enter(client, role)).json()
        assert me["username"] == username
    admin = enter(client, "admin")
    students = client.get("/students/", headers=admin).json()
    with sessions() as db:
        own = {s.email for s in db.query(Student).filter_by(institution_id=1)}
        demo = {s.email for s in db.query(Student).filter_by(institution_id=institution)}
    assert {s["email"] for s in students} <= demo and not (
        {s["email"] for s in students} & (own - demo)
    )
    # No pending legal dialog for visitors.
    assert client.get("/legal/pending", headers=admin).json() == {"documents": []}


def test_the_demo_never_emails_nor_sells_plans(demo_site):
    client, sessions, _tokens, _engine, _own, _permissions = demo_site
    with sessions() as db:
        set_tenant(db, demo_id(sessions))
        assert queue_email(db, "alguien@ejemplo.do", "Asunto", "Texto", category="notice") is None
    admin = enter(client, "admin")
    refused = client.post(
        "/billing/checkout", headers={**admin, **ORIGIN}, json={"plan_code": "basico"}
    )
    assert refused.status_code == 403 and "demo" in refused.json()["detail"]
    gateway = client.put(
        "/online-payments/config/gateway",
        headers=admin,
        json={"enabled": True, "gateway": "sandbox"},
    )
    assert gateway.status_code == 403


def test_the_demo_is_closed_unless_enabled(installation):  # noqa: F811
    client, _sessions, _tokens = installation
    assert client.get("/public/demo").json() == {"enabled": False, "roles": []}
    assert client.post("/public/demo/login", json={"role": "admin"}).status_code == 404
    assert client.post("/public/demo/login", json={"role": "root"}).status_code == 422
