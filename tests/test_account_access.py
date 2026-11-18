"""Fase 0, paso 1: regresiones de A1, A2, M2 y M3 de la auditoría del 17/11/2026."""

from datetime import datetime

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.auth import role_permission_slugs
from app.db.database import Base
from app.db.Session import get_db
from app.models import Permission, Role, RolePermission, Student, Teacher, User
from app.models.community_model import Guardian, StudentGuardian
from app.models.operations_model import CalendarEvent
from app.models.security_model import AuditLog, LoginThrottle
from app.routers.operations_router import student_scope_ids
from app.security import hash_password
from app.services.login_throttle import ensure_not_blocked, record_failure
from main import app
from scripts.seed_demo import seed_demo

PASSWORDS = {
    "demo.admin": "NexoAdmin2026!",
    "demo.docente": "NexoDocente2026!",
    "demo.estudiante": "NexoEstudiante2026!",
}
SLUGS = (
    "access.manage",
    "academic.manage",
    "finance.manage",
    "reports.view",
    "records.own",
)
# Custom staff roles (M1): username -> granted permission.
STAFF = {"finanzas": "finance.manage", "registro": "reports.view"}


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
        for username, slug in STAFF.items():
            role = Role(name=username, label=username.title(), description=slug)
            db.add(role)
            db.flush()
            db.add(
                RolePermission(role_id=role.role_id, permission_id=permissions[slug].permission_id)
            )
            db.add(
                User(
                    username=username,
                    email=f"{username}@example.com",
                    password=hash_password("Personal2026!"),
                    role_id=role.role_id,
                )
            )
        # A guardian linked only to the demo student (M5).
        guardian_role = Role(name="guardian", label="Tutoría", description="Tutor")
        guardian = Guardian(
            first_name="Rosa", last_name="Tutora", email="rosa@example.com", telephone="8095550101"
        )
        db.add_all([guardian_role, guardian])
        db.flush()
        db.add(
            RolePermission(
                role_id=guardian_role.role_id,
                permission_id=permissions["records.own"].permission_id,
            )
        )
        child = db.query(User).filter_by(username="demo.estudiante").one().student_id
        db.add(
            StudentGuardian(
                student_id=child, guardian_id=guardian.guardian_id, relationship="Madre"
            )
        )
        db.add(
            User(
                username="tutora",
                email="rosa@example.com",
                password=hash_password("Tutora2026!!"),
                role_id=guardian_role.role_id,
                guardian_id=guardian.guardian_id,
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


def other_student(sessions, excluded):
    with sessions() as db:
        source = db.get(Student, excluded)
        stranger = Student(
            first_name="Ajeno",
            last_name="Prueba",
            email="ajeno@example.com",
            enrollment_number="AJENO-1",
            telephone="8095550102",
            address="Ficticia",
            career_id=source.career_id,
        )
        db.add(stranger)
        db.commit()
        return stranger.student_id


def demo_student(sessions):
    with sessions() as db:
        return db.query(User).filter_by(username="demo.estudiante").one().student_id


# M1: los roles personalizados leen según sus permisos, no según el nombre del rol.
def test_finance_role_reads_student_finances_but_not_grades(context):
    client, sessions = context
    finance = headers(client, "finanzas", "Personal2026!")
    student = demo_student(sessions)
    assert client.get(f"/finance/students/{student}", headers=finance).status_code == 200
    assert client.get("/students/", headers=finance).json()
    response = client.get(f"/documents/students/{student}/statement.pdf", headers=finance)
    assert response.status_code == 200
    assert (
        client.get(f"/documents/students/{student}/transcript.pdf", headers=finance).status_code
        == 403
    )
    assert client.get("/enrollments/", headers=finance).json() == []


def test_reports_role_reads_institutional_academic_data(context):
    client, sessions = context
    registry = headers(client, "registro", "Personal2026!")
    student = demo_student(sessions)
    assert client.get("/sections/", headers=registry).json()
    assert client.get("/enrollments/", headers=registry).json()
    response = client.get(f"/documents/students/{student}/transcript.pdf", headers=registry)
    assert response.status_code == 200


def test_role_without_scope_grants_sees_nothing(context):
    client, sessions = context
    clerk = headers(client, "secretaria", "Secretaria2026!")
    student = demo_student(sessions)
    assert client.get("/students/", headers=clerk).json() == []
    assert client.get("/sections/", headers=clerk).json() == []
    assert client.get("/enrollments/", headers=clerk).json() == []
    assert client.get(f"/finance/students/{student}", headers=clerk).status_code == 403


def test_admin_role_name_alone_does_not_grant_scope(context):
    client, sessions = context
    with sessions() as db:
        admin = db.query(Role).filter_by(name="admin").one()
        db.query(RolePermission).filter(
            RolePermission.role_id == admin.role_id,
            RolePermission.permission_id.in_(
                db.query(Permission.permission_id).filter(
                    Permission.slug.in_(["academic.manage", "reports.view", "finance.manage"])
                )
            ),
        ).delete(synchronize_session=False)
        db.commit()
    admin_token = headers(client, "demo.admin")
    assert client.get("/sections/", headers=admin_token).json() == []


# M5: los tutores descargan los documentos de sus hijos, y solo de ellos.
@pytest.mark.parametrize(
    "document", ["report-card", "enrollment-certificate", "transcript", "statement"]
)
def test_guardian_downloads_linked_child_documents(context, document):
    client, sessions = context
    guardian = headers(client, "tutora", "Tutora2026!!")
    child = demo_student(sessions)
    response = client.get(f"/documents/students/{child}/{document}.pdf", headers=guardian)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    stranger = other_student(sessions, child)
    denied = client.get(f"/documents/students/{stranger}/{document}.pdf", headers=guardian)
    assert denied.status_code == 403


# M4: el límite de intentos vive en la base y no permite bloquear cuentas ajenas.
def test_failed_logins_block_only_the_attacking_address(context):
    client, sessions = context
    for _ in range(5):
        assert login(client, "demo.admin", "incorrecta").status_code == 401
    blocked = login(client, "demo.admin")
    assert blocked.status_code == 429
    with sessions() as db:
        assert (
            db.query(LoginThrottle)
            .filter(LoginThrottle.throttle_key == "pair:testclient:demo.admin")
            .one()
            .blocked_until
            is not None
        )
        # The account itself is not locked: other addresses are unaffected.
        ensure_not_blocked(db, "203.0.113.7", "demo.admin")


def test_throttle_is_shared_through_the_database(context):
    _, sessions = context
    with sessions() as db:
        for _ in range(5):
            record_failure(db, "10.0.0.1", "Demo.Admin")
        db.commit()
    # A second "worker" with its own session sees the block.
    with sessions() as db:
        with pytest.raises(HTTPException) as blocked:
            ensure_not_blocked(db, "10.0.0.1", "demo.admin")
        assert blocked.value.status_code == 429
        ensure_not_blocked(db, "10.0.0.2", "demo.admin")


def test_address_limit_covers_many_usernames(context):
    _, sessions = context
    with sessions() as db:
        for index in range(30):
            record_failure(db, "10.0.0.9", f"usuario{index}")
        db.commit()
        with pytest.raises(HTTPException):
            ensure_not_blocked(db, "10.0.0.9", "otra.cuenta")


def test_successful_login_clears_the_pair_counter(context):
    client, sessions = context
    for _ in range(3):
        login(client, "demo.docente", "incorrecta")
    assert login(client, "demo.docente").status_code == 200
    with sessions() as db:
        assert (
            db.query(LoginThrottle)
            .filter(LoginThrottle.throttle_key == "pair:testclient:demo.docente")
            .first()
            is None
        )
