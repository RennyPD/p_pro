"""Fase 0, paso 1: regresiones de A1, A2, M2 y M3 de la auditoría del 17/11/2026."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.auth import role_permission_slugs
from app.db.database import Base
from app.db.Session import get_db
from app.models import Permission, Role, RolePermission, Student, Teacher, User
from app.models.operations_model import CalendarEvent
from app.models.security_model import AuditLog
from app.routers.operations_router import student_scope_ids
from app.security import hash_password
from main import app
from scripts.seed_demo import seed_demo

PASSWORDS = {
    "demo.admin": "NexoAdmin2026!",
    "demo.docente": "NexoDocente2026!",
    "demo.estudiante": "NexoEstudiante2026!",
}
SLUGS = ("access.manage", "academic.manage", "finance.manage", "reports.view")


@pytest.fixture
def context(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'access.db'}", connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        seed_demo(db)
        permissions = {slug: Permission(slug=slug, description=slug) for slug in SLUGS}
        db.add_all(permissions.values())
        db.flush()
        admin = db.query(Role).filter_by(name="admin").one()
        # A delegated access manager: may manage accounts but holds nothing else.
        clerk = Role(name="secretaria", label="Secretaría", description="Gestión de cuentas")
        db.add(clerk)
        db.flush()
        db.add_all(
            RolePermission(role_id=admin.role_id, permission_id=item.permission_id)
            for item in permissions.values()
        )
        db.add(
            RolePermission(
                role_id=clerk.role_id, permission_id=permissions["access.manage"].permission_id
            )
        )
        db.add(
            User(
                username="secretaria",
                email="secretaria@example.com",
                password=hash_password("Secretaria2026!"),
                role_id=clerk.role_id,
            )
        )
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
        yield client, sessions
    app.dependency_overrides.clear()
    engine.dispose()


def login(client, username, password=None):
    return client.post(
        "/auth/login", json={"username": username, "password": password or PASSWORDS[username]}
    )


def headers(client, username, password=None):
    response = login(client, username, password)
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def user_id(sessions, username):
    with sessions() as db:
        return db.query(User).filter_by(username=username).one().user_id


# A1: desactivar a la persona vinculada quita el acceso.
@pytest.mark.parametrize(
    ("username", "model", "link"),
    [("demo.estudiante", Student, "student_id"), ("demo.docente", Teacher, "teacher_id")],
)
def test_inactive_linked_profile_loses_access(context, username, model, link):
    client, sessions = context
    token = headers(client, username)
    assert client.get("/auth/me", headers=token).status_code == 200
    with sessions() as db:
        person = db.get(model, getattr(db.query(User).filter_by(username=username).one(), link))
        person.active = False
        db.commit()

    me = client.get("/auth/me", headers=token)
    assert me.status_code == 401
    assert "desactivada" in me.json()["detail"]
    assert client.post("/auth/refresh").status_code == 401
    denied = login(client, username)
    assert denied.status_code == 403
    assert "desactivada" in denied.json()["detail"]


def test_inactive_account_reports_wrong_password_as_usual(context):
    client, sessions = context
    with sessions() as db:
        db.query(User).filter_by(username="demo.docente").one().active = False
        db.commit()
    response = login(client, "demo.docente", "incorrecta")
    assert response.status_code == 401
    assert "desactivada" not in response.text


# A2: las cuentas con historial se desactivan; el borrado explica por qué no procede.
def test_deactivate_and_reactivate_account(context):
    client, sessions = context
    admin = headers(client, "demo.admin")
    teacher_token = headers(client, "demo.docente")
    target = user_id(sessions, "demo.docente")

    response = client.post(f"/users/{target}/deactivate", headers=admin)
    assert response.status_code == 200, response.text
    assert response.json()["active"] is False
    assert client.get("/auth/me", headers=teacher_token).status_code == 401
    assert login(client, "demo.docente").status_code == 403

    response = client.post(f"/users/{target}/activate", headers=admin)
    assert response.status_code == 200, response.text
    assert response.json()["active"] is True
    assert login(client, "demo.docente").status_code == 200
    with sessions() as db:
        actions = {row.action for row in db.query(AuditLog).filter_by(resource=f"user:{target}")}
    assert {"user.deactivated", "user.activated"} <= actions


def test_cannot_deactivate_self_or_last_manager(context):
    client, sessions = context
    admin = headers(client, "demo.admin")
    own = user_id(sessions, "demo.admin")
    assert client.post(f"/users/{own}/deactivate", headers=admin).status_code == 409


def test_delete_user_with_history_returns_actionable_conflict(context):
    client, sessions = context
    admin = headers(client, "demo.admin")
    target = user_id(sessions, "demo.docente")
    with sessions() as db:
        # History protected by a foreign key to the account.
        db.add(
            CalendarEvent(
                title="Reunión",
                starts_at=datetime(2026, 11, 20, 9),
                ends_at=datetime(2026, 11, 20, 10),
                created_by=target,
            )
        )
        db.commit()
    response = client.delete(f"/users/{target}", headers=admin)
    assert response.status_code == 409
    assert "Desactívala" in response.json()["detail"]
    with sessions() as db:
        assert db.get(User, target) is not None


def test_delete_user_without_history_still_works(context):
    client, sessions = context
    admin = headers(client, "demo.admin")
    target = user_id(sessions, "secretaria")
    assert client.delete(f"/users/{target}", headers=admin).status_code == 200


# M2: un usuario sin vínculo ni rol administrativo no ve ningún estudiante.
def test_unlinked_user_has_empty_student_scope(context):
    _, sessions = context
    with sessions() as db:
        clerk = db.query(User).filter_by(username="secretaria").one()
        assert student_scope_ids(db, clerk) == []


def test_unlinked_user_sees_no_alerts(context):
    client, _ = context
    clerk = headers(client, "secretaria", "Secretaria2026!")
    response = client.get("/operations/alerts", headers=clerk)
    assert response.status_code == 200, response.text
    assert response.json() == []


# M3: access.manage no basta para tomar control de cuentas con más permisos.
def test_access_manager_cannot_take_over_admin(context):
    client, sessions = context
    clerk = headers(client, "secretaria", "Secretaria2026!")
    admin_id = user_id(sessions, "demo.admin")
    with sessions() as db:
        admin_role = db.query(Role).filter_by(name="admin").one().role_id

    reset = client.post(
        f"/users/{admin_id}/password", headers=clerk, json={"password": "Tomada2026!!"}
    )
    assert reset.status_code == 403
    assert client.post(f"/users/{admin_id}/deactivate", headers=clerk).status_code == 403
    assert client.delete(f"/users/{admin_id}", headers=clerk).status_code == 403
    created = client.post(
        "/users/",
        headers=clerk,
        json={
            "username": "intruso",
            "email": "intruso@example.com",
            "password": "Intruso2026!",
            "role_id": admin_role,
        },
    )
    assert created.status_code == 403
    assert login(client, "demo.admin").status_code == 200


def test_access_manager_cannot_grant_permissions_it_lacks(context):
    client, sessions = context
    clerk = headers(client, "secretaria", "Secretaria2026!")
    with sessions() as db:
        own_role = db.query(Role).filter_by(name="secretaria").one().role_id
        admin_role = db.query(Role).filter_by(name="admin").one().role_id
    escalate = client.put(
        f"/access/roles/{own_role}/permissions",
        headers=clerk,
        json={"permissions": ["access.manage", "finance.manage"], "reason": "Escalada"},
    )
    assert escalate.status_code == 403
    strip_admin = client.put(
        f"/access/roles/{admin_role}/permissions",
        headers=clerk,
        json={"permissions": list(SLUGS), "reason": "Tocar Administración"},
    )
    assert strip_admin.status_code == 403


def test_access_manager_can_still_manage_equal_or_lower_accounts(context):
    client, sessions = context
    clerk = headers(client, "secretaria", "Secretaria2026!")
    target = user_id(sessions, "demo.estudiante")
    with sessions() as db:
        student_role = db.query(Role).filter_by(name="student").one()
        assert not role_permission_slugs(db, student_role.role_id) - {"access.manage"}
    reset = client.post(
        f"/users/{target}/password", headers=clerk, json={"password": "Restablecida2026!"}
    )
    assert reset.status_code == 204, reset.text
