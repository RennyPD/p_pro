"""Isolation between institutions (Fase 4, block A).

A second institution with its own administrator (same username as the demo's)
must never see, change or count the demo institution's data.
"""

import pytest
from db_support import TEST_DATABASE_URL, reset_schema
from sqlalchemy import create_engine, text
from test_route_permissions import routes
from test_write_audit import demo  # noqa: F401  (shared fixture)

from app.db.tenant import TenantError, mark_request, set_tenant
from app.models import (
    AcademicPeriod,
    Career,
    Institution,
    Role,
    Section,
    Student,
    Teacher,
    User,
)
from app.security import hash_password

SECOND_PASSWORD = "SegundaAdmin2026!"


def second_institution(sessions):
    with sessions() as db:
        db.add(
            Institution(institution_id=2, name="Colegio Segundo", slug="segundo", status="active")
        )
        db.commit()
    with sessions() as db:
        set_tenant(db, 2)
        role = Role(name="admin", description="Administración")
        db.add(role)
        db.flush()
        career = Career(name="Bachillerato Segundo", description="Programa", code="SEG-01")
        db.add(career)
        db.flush()
        db.add(
            User(
                username="demo.admin",
                email="admin@segundo.edu.do",
                password=hash_password(SECOND_PASSWORD),
                role_id=role.role_id,
            )
        )
        db.add(
            Student(
                first_name="Solo",
                last_name="Segundo",
                email="solo@segundo.edu.do",
                enrollment_number="SEG-0001",
                telephone="809",
                address="SD",
                career_id=career.career_id,
            )
        )
        db.commit()


def markers(sessions) -> list[str]:
    """Values that only exist in the demo institution."""
    with sessions() as db:
        set_tenant(db, 1)
        values = [s.email for s in db.query(Student)]
        values += [s.enrollment_number for s in db.query(Student)]
        values += [t.email for t in db.query(Teacher)]
        values += [s.code for s in db.query(Section)]
    return [value for value in values if value and len(value) > 4]


def login(client, institution=None, password=SECOND_PASSWORD):
    body = {"username": "demo.admin", "password": password}
    if institution:
        body["institution"] = institution
    return client.post("/auth/login", json=body)


@pytest.fixture
def tenants(demo):  # noqa: F811
    client, sessions, tokens = demo
    second_institution(sessions)
    response = login(client, "segundo")
    assert response.status_code == 200, response.text
    second = {"Authorization": "Bearer " + response.json()["access_token"]}
    return client, sessions, tokens, second


def test_sign_in_asks_for_the_institution_when_the_username_repeats(tenants):
    client, _sessions, _tokens, _second = tenants
    ambiguous = login(client)
    assert ambiguous.status_code == 409 and "código de tu institución" in ambiguous.json()["detail"]
    assert login(client, "principal", "NexoAdmin2026!").status_code == 200
    assert login(client, "principal").status_code == 401  # second's password, first institution
    assert login(client, "no-existe").status_code == 401


def test_every_listing_hides_the_other_institution(tenants):
    client, sessions, _tokens, second = tenants  # noqa: RUF059
    secret = markers(sessions)
    assert len(secret) >= 5
    leaks, checked = [], 0
    for method, path, _route in routes():
        if method != "GET" or "{" in path or path.startswith(("/docs", "/openapi", "/redoc")):
            continue
        response = client.get(path, headers=second)
        if response.status_code != 200:
            continue
        checked += 1
        found = [value for value in secret if value in response.text]
        if found:
            leaks.append(f"{path}: {found[:3]}")
    assert checked > 40, checked  # the scan really covers the application
    # Control: the demo administrator does see those values on several screens,
    # so the scan would catch a leak.
    own = 0
    for method, path, _route in routes():
        if method != "GET" or "{" in path or path.startswith(("/docs", "/openapi", "/redoc")):
            continue
        response = client.get(path, headers=_tokens["admin"])
        if response.status_code == 200 and any(value in response.text for value in secret):
            own += 1
    assert own >= 5, own
    assert leaks == [], "Datos de otra institución visibles:\n" + "\n".join(leaks)
    students = client.get("/students/", headers=second).json()
    assert [s["email"] for s in students] == ["solo@segundo.edu.do"]


def test_records_of_another_institution_do_not_exist(tenants):
    client, sessions, tokens, second = tenants
    with sessions() as db:
        student = db.query(Student).filter(Student.institution_id == 1).first().student_id
        section = db.query(Section).filter(Section.institution_id == 1).first().section_id
    assert client.get(f"/students/{student}", headers=second).status_code == 404
    edit = client.patch(f"/students/{student}", headers=second, json={"telephone": "1"})
    assert edit.status_code == 404
    assert client.get(f"/sections/{section}", headers=second).status_code == 404
    with sessions() as db:
        assert db.get(Student, student).telephone != "1"
    # The demo administrator still sees its own student.
    assert client.get(f"/students/{student}", headers=tokens["admin"]).status_code == 200


def test_uniques_are_per_institution_and_bulk_updates_stay_inside(tenants):
    client, sessions, tokens, second = tenants
    with sessions() as db:
        taken = db.query(Student).filter(Student.institution_id == 1).first()
        email, career = taken.email, None
        set_tenant(db, 2)
        career = db.query(Career).first().career_id
    created = client.post(
        "/students/",
        headers=second,
        json={
            "first_name": "Mismo",
            "last_name": "Correo",
            "email": email,
            "telephone": "809",
            "address": "SD",
            "career_id": career,
        },
    )
    assert created.status_code == 200, created.text
    period = client.post(
        "/periods/",
        headers=second,
        json={
            "name": "2027-1",
            "start_date": "2027-01-10",
            "end_date": "2027-05-20",
            "active": True,
            "academic_year": "2027",
        },
    )
    assert period.status_code == 200, period.text
    with sessions() as db:
        # Marking the new period active deactivates only the second institution's periods.
        assert db.query(AcademicPeriod).filter_by(institution_id=1, active=True).count() >= 1


def test_request_without_institution_sees_nothing_and_cannot_write(demo):  # noqa: F811
    _client, sessions, _tokens = demo
    with sessions() as db:
        mark_request(db)
        assert db.query(Student).all() == []
        assert db.get(Student, 1) is None
        db.add(
            Teacher(
                first_name="X",
                last_name="Y",
                specialty="Z",
                email="x@y.do",
                telephone="1",
                address="a",
            )
        )
        with pytest.raises(TenantError):
            db.flush()
        db.rollback()
    with sessions() as db:
        set_tenant(db, 1)
        with pytest.raises(TenantError):
            set_tenant(db, 2)


def test_writes_and_locks_carry_the_institution(tenants):
    client, sessions, _tokens, second = tenants
    with sessions() as db:
        set_tenant(db, 2)
        foreign = Student(
            institution_id=1,
            first_name="Intruso",
            last_name="X",
            email="intruso@x.do",
            enrollment_number="X-1",
            telephone="1",
            address="a",
            career_id=1,
        )
        db.add(foreign)
        with pytest.raises(TenantError):
            db.flush()
        db.rollback()
    from app.services.write_locks import lock_scope

    with sessions() as db:
        set_tenant(db, 2)
        lock_scope(db, "academic")
        db.commit()
        keys = {row[0] for row in db.execute(text("SELECT lock_key FROM write_locks"))}
    assert "2:academic" in keys


@pytest.mark.skipif(TEST_DATABASE_URL is None, reason="Requiere PostgreSQL (Row-Level Security)")
def test_row_level_security_backs_up_the_application(tmp_path, monkeypatch):
    from alembic.config import Config

    from alembic import command
    from app.db import database

    engine = create_engine(TEST_DATABASE_URL)
    reset_schema(engine)
    monkeypatch.setattr(database, "DATABASE_URL", TEST_DATABASE_URL)
    command.upgrade(Config("alembic.ini"), "head")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO institutions (institution_id, name, slug, status, created_at) "
                "VALUES (2, 'Otra', 'otra', 'active', CURRENT_TIMESTAMP)"
            )
        )
        for institution in (1, 2):
            connection.execute(
                text(
                    "INSERT INTO subjects (institution_id, code, description) "
                    "VALUES (:i, 'MAT-101', 'Matemática')"
                ),
                {"i": institution},
            )
        connection.execute(text("DROP ROLE IF EXISTS nexo_rls_test"))
        connection.execute(text("CREATE ROLE nexo_rls_test"))
        connection.execute(text("GRANT USAGE ON SCHEMA public TO nexo_rls_test"))
        connection.execute(
            text("GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA public TO nexo_rls_test")
        )
    with engine.connect() as connection:
        connection.execute(text("SET ROLE nexo_rls_test"))

        def visible(institution=None, bypass="off"):
            connection.execute(
                text(
                    "SELECT set_config('app.institution_id', :i, false), set_config('app.tenant_bypass', :b, false)"
                ),
                {"i": str(institution or ""), "b": bypass},
            )
            return sorted(
                row[0] for row in connection.execute(text("SELECT institution_id FROM subjects"))
            )

        assert visible(2) == [2]
        assert visible(1) == [1]
        assert visible() == []  # no institution: nothing
        assert visible(bypass="on") == [1, 2]  # system jobs
        connection.execute(
            text(
                "SELECT set_config('app.institution_id', '2', false), set_config('app.tenant_bypass', 'off', false)"
            )
        )
        with pytest.raises(Exception):
            connection.execute(
                text(
                    "INSERT INTO subjects (institution_id, code, description) VALUES (1, 'X', 'Y')"
                )
            )
        connection.rollback()
        connection.execute(text("RESET ROLE"))
        connection.execute(text("DROP OWNED BY nexo_rls_test"))
        connection.execute(text("DROP ROLE nexo_rls_test"))
        connection.commit()
    engine.dispose()
