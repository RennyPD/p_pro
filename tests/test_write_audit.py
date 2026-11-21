"""Sensitive writes leave an audit entry with actor and action (audit A2, rule 11).

Each case changes something through the API and checks the ``audit_logs`` row
written in the same transaction. ``tests/test_route_audit.py`` makes sure new
write routes record something; these cases check that the important ones record
the right thing.
"""

import pytest
from db_support import make_engine
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.Session import get_db
from app.models import Role, Student, User
from app.models.security_model import AuditLog
from main import app
from scripts.seed_demo import seed_demo


@pytest.fixture
def demo(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'audit.db'}", connect_args={"timeout": 15})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        seed_demo(db)
        db.commit()

    def override():
        with sessions() as db:
            try:
                yield db
            except Exception:
                db.rollback()
                raise

    app.dependency_overrides[get_db] = override
    with TestClient(app) as client:
        tokens = {}
        for role, password in (
            ("admin", "Admin"),
            ("docente", "Docente"),
            ("estudiante", "Estudiante"),
        ):
            response = client.post(
                "/auth/login",
                json={"username": f"demo.{role}", "password": f"Nexo{password}2026!"},
            )
            assert response.status_code == 200, response.text
            tokens[role] = {"Authorization": "Bearer " + response.json()["access_token"]}
        yield client, sessions, tokens
    app.dependency_overrides.clear()
    engine.dispose()


def entries(sessions, action, resource=None):
    with sessions() as db:
        query = db.query(AuditLog).filter_by(action=action)
        if resource is not None:
            query = query.filter_by(resource=resource)
        return [
            (db.get(User, row.user_id).username if row.user_id else None, row.resource, row.detail)
            for row in query.order_by(AuditLog.audit_log_id)
        ]


def a_student(sessions):
    with sessions() as db:
        student = db.query(Student).filter_by(active=True).order_by(Student.student_id).first()
        return student.student_id, student.career_id


# Lote 1: estudiantes, cuentas, roles e importación.


def test_student_holds_and_status_are_audited_with_before_and_after(demo):
    client, sessions, tokens = demo
    student_id, _ = a_student(sessions)

    response = client.patch(
        f"/students/{student_id}",
        headers=tokens["admin"],
        json={"academic_hold": True, "financial_hold": True, "active": False},
    )
    assert response.status_code == 200, response.text

    [(actor, resource, detail)] = entries(sessions, "student.updated")
    assert (actor, resource) == ("demo.admin", f"student:{student_id}")
    assert "academic_hold: no → sí" in detail
    assert "financial_hold: no → sí" in detail
    assert "active: sí → no" in detail


def test_student_create_and_deactivate_are_audited(demo):
    client, sessions, tokens = demo
    _, career_id = a_student(sessions)
    created = client.post(
        "/students/",
        headers=tokens["admin"],
        json={
            "first_name": "Ana",
            "last_name": "Auditoría",
            "email": "ana.auditoria@example.com",
            "telephone": "8095550100",
            "address": "Calle 1",
            "career_id": career_id,
        },
    )
    assert created.status_code == 200, created.text
    student_id = created.json()["student_id"]
    assert client.delete(f"/students/{student_id}", headers=tokens["admin"]).status_code == 200

    [(actor, _, detail)] = entries(sessions, "student.created", f"student:{student_id}")
    assert actor == "demo.admin" and "Ana Auditoría" in detail
    assert entries(sessions, "student.deactivated", f"student:{student_id}")[0][0] == "demo.admin"


def test_rejected_student_change_leaves_no_entry(demo):
    client, sessions, tokens = demo
    student_id, _ = a_student(sessions)
    denied = client.patch(
        f"/students/{student_id}", headers=tokens["estudiante"], json={"academic_hold": True}
    )
    assert denied.status_code == 403
    assert entries(sessions, "student.updated") == []


def test_user_creation_and_role_edits_are_audited(demo):
    client, sessions, tokens = demo
    created = client.post(
        "/roles/",
        headers=tokens["admin"],
        json={"name": "auditor", "description": "Revisa registros", "label": "Auditor"},
    )
    assert created.status_code == 200, created.text
    role_id = created.json()["role_id"]

    updated = client.patch(
        f"/roles/{role_id}", headers=tokens["admin"], json={"label": "Auditoría interna"}
    )
    assert updated.status_code == 200, updated.text
    [(actor, _, detail)] = entries(sessions, "role.updated", f"role:{role_id}")
    assert actor == "demo.admin" and "label: Auditor → Auditoría interna" in detail

    with sessions() as db:
        staff_role = db.query(Role).filter_by(name="auditor").one().role_id
    account = client.post(
        "/users/",
        headers=tokens["admin"],
        json={
            "username": "nuevo.auditor",
            "email": "nuevo.auditor@example.com",
            "password": "una-clave-segura-2026",
            "role_id": staff_role,
        },
    )
    assert account.status_code == 200, account.text
    user_id = account.json()["user_id"]
    [(actor, _, detail)] = entries(sessions, "user.created", f"user:{user_id}")
    assert actor == "demo.admin" and "nuevo.auditor" in detail
    assert "una-clave-segura" not in detail

    assert client.delete(f"/users/{user_id}", headers=tokens["admin"]).status_code == 200
    assert client.delete(f"/roles/{role_id}", headers=tokens["admin"]).status_code == 200
    assert entries(sessions, "role.deleted", f"role:{role_id}") == [
        ("demo.admin", f"role:{role_id}", "auditor")
    ]


def test_bulk_import_records_one_summary_and_dry_run_records_nothing(demo):
    client, sessions, tokens = demo
    _, career_id = a_student(sessions)
    content = (
        "first_name,last_name,email,telephone,address,career_id\n"
        f"Luis,Lote,luis.lote@example.com,8095550100,Calle 2,{career_id}\n"
        f"Eva,Lote,eva.lote@example.com,8095550100,Calle 3,{career_id}\n"
    ).encode()
    headers = {**tokens["admin"], "Content-Type": "text/csv"}

    preview = client.post("/bulk/students/import?dry_run=true", headers=headers, content=content)
    assert preview.status_code == 200, preview.text
    assert entries(sessions, "students.imported") == []

    imported = client.post("/bulk/students/import", headers=headers, content=content)
    assert imported.status_code == 200, imported.text
    [(actor, _, detail)] = entries(sessions, "students.imported")
    assert actor == "demo.admin"
    assert detail.startswith("Creados: 2; rechazados: 0")
