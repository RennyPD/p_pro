from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from alembic import command
from app.db import database
from app.db.Session import get_db
from app.models.assessment_model import Assessment
from app.models.finance_model import Charge, StudentAccount
from app.models.role_model import Role
from app.models.section_model import Section
from app.models.student_model import Student
from app.models.user_model import User
from app.services.business_time import business_date
from app.services.finance_workflow import summary
from main import app
from scripts.seed_demo import seed_demo


@pytest.fixture
def migrated_engine(tmp_path, monkeypatch):
    database_url = f"sqlite:///{(tmp_path / 'installation.db').as_posix()}"
    monkeypatch.setattr(database, "DATABASE_URL", database_url)
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(database_url)

    def get_test_db():
        with Session(engine) as session:
            yield session

    monkeypatch.setitem(app.dependency_overrides, get_db, get_test_db)
    yield engine
    engine.dispose()


def test_initial_admin_and_account_validation_on_migrated_database(migrated_engine):
    engine = migrated_engine
    try:
        with TestClient(app) as client:
            account = {
                "username": "primer-admin-qa",
                "email": "primer-admin@example.com",
                "password": "clave-ficticia-de-prueba",
            }
            response = client.post("/auth/bootstrap", json={**account, "password": "corta"})
            assert response.status_code == 422
            assert "corta" not in response.text
            response = client.post("/auth/bootstrap", json=account)
            assert response.status_code == 201
            headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
            user_id = response.json()["user"]["user_id"]
            assert client.get("/users/", headers=headers).status_code == 200
            assert client.post("/auth/bootstrap", json=account).status_code == 409

            response = client.post(
                "/users/",
                headers=headers,
                json={**account, "role_id": 1, "student_id": 23, "teacher_id": 24},
            )
            assert response.status_code == 422
            assert account["password"] not in response.text
            assert all(set(error) == {"loc", "type", "msg"} for error in response.json()["detail"])
            response = client.patch(f"/users/{user_id}", headers=headers, json={"password": None})
            assert response.status_code == 422
            assert response.json()["detail"][0]["loc"] == ["body", "password"]
            assert (
                client.patch(
                    f"/users/{user_id}", headers=headers, json={"student_id": 23}
                ).status_code
                == 422
            )
            with Session(engine) as db:
                teacher_role = Role(name="teacher", description="Perfil docente QA")
                db.add(teacher_role)
                db.flush()
                role_id = teacher_role.role_id
                db.commit()
            response = client.post(
                "/users/",
                headers=headers,
                json={
                    **account,
                    "username": "docente-qa",
                    "email": "docente@example.com",
                    "role_id": role_id,
                    "teacher_id": 999,
                },
            )
            assert response.status_code == 422
    finally:
        engine.dispose()


def test_assessment_creation_and_lifecycle_writes_are_serialized(migrated_engine):
    with TestClient(app) as client:
        admin = client.post(
            "/auth/bootstrap",
            json={
                "username": "evaluaciones-qa",
                "email": "evaluaciones@example.com",
                "password": "clave-evaluaciones-qa",
            },
        )
        assert admin.status_code == 201
        headers = {"Authorization": f"Bearer {admin.json()['access_token']}"}
    with Session(migrated_engine) as db:
        seed_demo(db)
        section = db.query(Section).order_by(Section.section_id).first()
        section_id = section.section_id
        enrollment_ids = [
            item.enrollment_id for item in section.enrollments if item.state == "enrolled"
        ]
        assert enrollment_ids
    with TestClient(app) as client:

        def concurrently(*actions):
            barrier = Barrier(len(actions), timeout=10)

            def run(action):
                with TestClient(app) as worker:
                    barrier.wait()
                    method, target, payload = action
                    return worker.request(method, target, headers=headers, json=payload)

            with ThreadPoolExecutor(max_workers=len(actions)) as executor:
                return list(executor.map(run, actions))

        first, second = concurrently(
            *(
                ("POST", "/assessments/", {"section_id": section_id, "name": name, "weight": 60})
                for name in ("Ponderación A", "Ponderación B")
            )
        )
        assert sorted([first.status_code, second.status_code]) == [200, 422]
        stored = next(item.json() for item in (first, second) if item.status_code == 200)
        identifier = stored["assessment_id"]
        assessment = f"/assessments/{identifier}"
        with Session(migrated_engine) as db:
            weights = [
                item.weight for item in db.query(Assessment).filter_by(section_id=section_id)
            ]
            assert weights == [60]
        draft = client.post(
            "/grades/bulk",
            headers=headers,
            json={
                "section_id": section_id,
                "assessment_id": identifier,
                "grade_type": stored["name"],
                "date_recorded": business_date().isoformat(),
                "reason": "Borrador QA",
                "status": "draft",
                "records": [
                    {"enrollment_id": enrollment_id, "grade_value": 0}
                    for enrollment_id in enrollment_ids
                ],
            },
        )
        assert draft.status_code == 200
        published, closed = concurrently(
            ("POST", f"/grades/assessments/{identifier}/publish", None),
            ("POST", f"{assessment}/close", None),
        )
        assert published.status_code == 200
        assert closed.status_code in {200, 409}
        if closed.status_code == 409:
            assert client.post(f"{assessment}/close", headers=headers).status_code == 200
        reopened, edited = concurrently(
            ("POST", f"{assessment}/reopen", {"reason": "Revisión QA"}),
            ("PATCH", assessment, {"weight": 70}),
        )
        assert reopened.status_code == 200
        assert edited.status_code in {200, 409}
        with Session(migrated_engine) as db:
            item = db.get(Assessment, identifier)
            assert item.closed is False
            assert item.weight == (70 if edited.status_code == 200 else 60)


def test_production_requires_a_nondefault_secret_and_explicit_https_origins():
    with pytest.raises(ValueError):
        database.Settings(app_environment="production", _env_file=None)
    key = "clave-exclusiva-de-la-fixture-de-produccion"
    with pytest.raises(ValueError):
        database.Settings(
            app_environment="production", secret_key=key, cors_origins="*", _env_file=None
        )
    settings = database.Settings(
        app_environment="production",
        secret_key=key,
        cors_origins="https://nexo.example.com",
        _env_file=None,
    )
    assert settings.secure_cookies
    assert settings.cors_origin_regex is None


def test_account_migrations_preserve_legacy_mfa_and_academic_financial_rows(migrated_engine):
    with Session(migrated_engine) as db:
        seed_demo(db)
        user = db.query(User).filter_by(username="demo.admin").one()
        user.mfa_secret = "FACTORFICTICIO"
        user.mfa_enabled = True
        student = db.query(Student).order_by(Student.student_id).first()
        account = StudentAccount(student_id=student.student_id)
        db.add(account)
        db.flush()
        db.add(
            Charge(
                student_account_id=account.student_account_id,
                amount=325.50,
                description="Cargo ficticio QA",
                due_date=business_date(),
            )
        )
        db.commit()
        uid, account_id = user.user_id, account.student_account_id

    cfg = Config("alembic.ini")
    command.downgrade(cfg, "20261014_0032")
    with migrated_engine.connect() as db:
        before = db.execute(
            text(
                "SELECT (SELECT COUNT(*) FROM enrollments), (SELECT COUNT(*) FROM grades), "
                "(SELECT SUM(credits) FROM curriculum_courses), (SELECT SUM(amount) FROM charges)"
            )
        ).one()
        assert db.execute(text("PRAGMA foreign_key_check")).first() is None
    command.upgrade(cfg, "head")
    with migrated_engine.connect() as db:
        after = db.execute(
            text(
                "SELECT (SELECT COUNT(*) FROM enrollments), (SELECT COUNT(*) FROM grades), "
                "(SELECT SUM(credits) FROM curriculum_courses), (SELECT SUM(amount) FROM charges)"
            )
        ).one()
        assert after == before
        assert db.execute(text("PRAGMA foreign_key_check")).first() is None
        assert db.execute(text("PRAGMA integrity_check")).scalar() == "ok"
    with Session(migrated_engine) as db:
        user = db.get(User, uid)
        assert user.mfa_enabled and user.mfa_secret == "FACTORFICTICIO"
        assert user.mfa_pending_secret is None
        assert summary(db.get(StudentAccount, account_id)).balance == 325.50
