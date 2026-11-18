"""Regression cases from the institutional audit, using independent databases."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, time
from threading import Barrier
from unittest.mock import patch

import pytest
from db_support import TEST_DATABASE_URL, make_engine
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.Session import get_db
from app.models import (
    AcademicPeriod,
    CurriculumCourse,
    Enrollment,
    Permission,
    Role,
    RolePermission,
    Section,
    Student,
    Teacher,
)
from app.schemas.enrollment_schema import EnrollmentCreate
from app.services.enrollment_service import create_enrollment_service
from main import app
from scripts.seed_demo import seed_demo


@pytest.fixture
def institution(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'regression.db'}", connect_args={"timeout": 15})

    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        seed_demo(db)
        source = db.query(Section).filter_by(code="PROG-101-A").one()
        section = Section(
            code="AUD-ONE",
            description="Un cupo",
            teacher_id=source.teacher_id,
            subject_id=source.subject_id,
            days_of_week="Viernes",
            start_time=time(20),
            end_time=time(21),
            capacity=1,
            period_name="2026-2027",
            status="active",
        )
        db.add(section)
        db.flush()
        ids = []
        for i in range(4):
            student = Student(
                first_name="Prueba",
                last_name=str(i),
                email=f"audit{i}@example.com",
                enrollment_number=f"AUD-{i}",
                telephone="8095550100",
                address="Ficticia",
                career_id=db.query(Student).first().career_id,
            )
            db.add(student)
            db.flush()
            ids.append(student.student_id)
        db.commit()
        section_id = section.section_id

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
                "/auth/login", json={"username": f"demo.{role}", "password": f"Nexo{password}2026!"}
            )
            assert response.status_code == 200, response.text
            tokens[role] = {"Authorization": "Bearer " + response.json()["access_token"]}
        yield client, sessions, section_id, ids, tokens
    app.dependency_overrides.clear()
    engine.dispose()


def select(context, student):
    client, _, section, _, tokens = context
    response = client.post(
        "/enrollments/",
        headers=tokens["admin"],
        json={"student_id": student, "section_id": section, "period": "2026-2027"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_concurrent_last_seat_and_duplicate_subject(institution):
    _, sessions, section, students, _ = institution
    for _ in range(3):
        with sessions() as db:
            db.query(Enrollment).filter_by(section_id=section).delete()
            db.commit()
        barrier = Barrier(2)

        def enroll(student):
            with sessions() as db:
                barrier.wait(timeout=10)
                return create_enrollment_service(
                    db, EnrollmentCreate(student_id=student, section_id=section, period="2026-2027")
                ).state

        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(enroll, students[:2]))
        assert sorted(results) == ["enrolled", "waitlisted"]
    client, _, _, _, tokens = institution
    retry = client.post(
        "/enrollments/",
        headers=tokens["admin"],
        json={"student_id": students[0], "section_id": section, "period": "2026-2027"},
    )
    assert retry.status_code == 409


def test_withdrawal_is_idempotent_and_promotion_revalidates_hold(institution):
    client, sessions, section, students, tokens = institution
    a, b, c = [select(institution, s) for s in students[:3]]
    with sessions() as db:
        db.get(Student, students[1]).financial_hold = True
        db.commit()
    for _ in range(2):
        result = client.patch(
            f"/enrollments/{a['enrollment_id']}",
            headers=tokens["admin"],
            json={"state": "withdrawn"},
        )
        assert result.status_code == 200, result.text
    with sessions() as db:
        assert db.get(Enrollment, b["enrollment_id"]).state == "waitlisted"
        assert db.get(Enrollment, c["enrollment_id"]).state == "enrolled"
        assert db.query(Enrollment).filter_by(section_id=section, state="enrolled").count() == 1


@pytest.mark.parametrize(
    "restriction",
    [
        "inactive",
        "academic_hold",
        "registration",
        "prerequisite",
        "credits",
        "schedule",
        "meetings",
    ],
)
def test_promotion_checks_current_eligibility(institution, restriction):
    client, sessions, _, students, tokens = institution
    a, b = [select(institution, s) for s in students[:2]]
    with sessions() as db:
        student = db.get(Student, students[1])
        if restriction == "inactive":
            student.active = False
        elif restriction == "academic_hold":
            student.academic_hold = True
        elif restriction == "registration":
            db.query(AcademicPeriod).filter_by(name="2026-2027").one().registration_end = date(
                2000, 1, 1
            )
        elif restriction == "prerequisite":
            course = (
                db.query(CurriculumCourse)
                .filter_by(subject_id=db.get(Section, a["section_id"]).subject_id)
                .one()
            )
            other = (
                db.query(CurriculumCourse)
                .filter(CurriculumCourse.subject_id != course.subject_id)
                .first()
            )
            course.prerequisite_subject_id = other.subject_id
        else:
            from app.models.configuration_model import InstitutionSettings

            source = db.get(Section, a["section_id"])
            other = db.query(Section).filter(Section.subject_id != source.subject_id).first()
            if restriction == "credits":
                settings = db.get(InstitutionSettings, 1)
                if settings is None:
                    settings = InstitutionSettings(settings_id=1)
                    db.add(settings)
                settings.max_credits_per_period = 1
            else:
                if restriction == "meetings":
                    from app.models.scheduling_model import SectionMeeting

                    for target in (source, other):
                        db.add(
                            SectionMeeting(
                                section_id=target.section_id,
                                day_of_week="Sábado",
                                start_time=time(18),
                                end_time=time(19),
                            )
                        )
                else:
                    other.days_of_week, other.start_time, other.end_time = (
                        source.days_of_week,
                        source.start_time,
                        source.end_time,
                    )
                db.add(
                    Enrollment(
                        student_id=student.student_id,
                        section_id=other.section_id,
                        period="2026-2027",
                        state="enrolled",
                    )
                )
        db.commit()
    response = client.patch(
        f"/enrollments/{a['enrollment_id']}", headers=tokens["admin"], json={"state": "withdrawn"}
    )
    assert response.status_code == 200, response.text
    with sessions() as db:
        assert db.get(Enrollment, b["enrollment_id"]).state == "waitlisted"


def test_withdrawal_and_promotion_rollback_together(institution):
    client, sessions, _, students, tokens = institution
    a, b = [select(institution, s) for s in students[:2]]
    with patch(
        "app.services.enrollment_service.promote_waitlist",
        side_effect=HTTPException(409, "Injected failure"),
    ):
        response = client.patch(
            f"/enrollments/{a['enrollment_id']}",
            headers=tokens["admin"],
            json={"state": "withdrawn"},
        )
    assert response.status_code == 409
    with sessions() as db:
        assert db.get(Enrollment, a["enrollment_id"]).state == "enrolled"
        assert db.get(Enrollment, b["enrollment_id"]).state == "waitlisted"


def test_waitlist_keeps_priority_when_a_candidate_regains_eligibility(institution):
    client, sessions, _, students, tokens = institution
    a, b = [select(institution, s) for s in students[:2]]
    with sessions() as db:
        db.get(Student, students[1]).financial_hold = True
        db.commit()
    assert (
        client.patch(
            f"/enrollments/{a['enrollment_id']}",
            headers=tokens["admin"],
            json={"state": "withdrawn"},
        ).status_code
        == 200
    )
    with sessions() as db:
        db.get(Student, students[1]).financial_hold = False
        db.commit()
    c = select(institution, students[2])
    assert c["state"] == "waitlisted"
    with sessions() as db:
        assert db.get(Enrollment, b["enrollment_id"]).state == "enrolled"


def test_period_invariants_and_internal_repository(institution):
    client, sessions, section, students, tokens = institution
    for period in ("MISSING", "OTHER"):
        with sessions() as db:
            if period == "OTHER":
                db.add(
                    AcademicPeriod(
                        name=period,
                        start_date=date(2026, 1, 1),
                        end_date=date(2026, 12, 31),
                        status="active",
                    )
                )
                db.commit()
        response = client.post(
            "/enrollments/",
            headers=tokens["admin"],
            json={"student_id": students[0], "section_id": section, "period": period},
        )
        assert response.status_code == 409
    from app.repositories.enrollment_repository import create_enrollment

    with sessions() as db:
        with pytest.raises(HTTPException):
            create_enrollment(
                db, EnrollmentCreate(student_id=students[0], section_id=section, period="MISSING")
            )
        db.rollback()
    a = select(institution, students[0])
    for changes in (
        {"period": "MISSING"},
        {"section_id": 99999},
        {"state": None},
        {"state": "completed"},
    ):
        assert client.patch(
            f"/enrollments/{a['enrollment_id']}", headers=tokens["admin"], json=changes
        ).status_code in {409, 422}
    with sessions() as db:
        assert db.query(Enrollment).filter_by(section_id=section).count() == 1


def test_legacy_teacher_permission_cannot_manage_offer_or_foreign_records(institution):
    client, sessions, section, students, tokens = institution
    a = select(institution, students[0])
    with sessions() as db:
        role = db.query(Role).filter_by(name="teacher").one()
        permission = Permission(slug="academic.manage", description="Legacy grant")
        db.add(permission)
        db.flush()
        db.add(RolePermission(role_id=role.role_id, permission_id=permission.permission_id))
        other_teacher = Teacher(
            first_name="Otro",
            last_name="Docente",
            email="otro@example.com",
            specialty="Prueba",
            telephone="123",
            address="Ficticia",
        )
        db.add(other_teacher)
        db.flush()
        db.get(Section, section).teacher_id = other_teacher.teacher_id
        db.commit()
    from scripts.seed_guardian_portal import seed_guardians

    with sessions() as db:
        seed_guardians(db, limit=1)
    guardian = client.post(
        "/auth/login", json={"username": "tutor.01", "password": "NexoTutor2026!"}
    )
    assert guardian.status_code == 200
    tokens["guardian"] = {"Authorization": "Bearer " + guardian.json()["access_token"]}
    for profile in ("docente", "estudiante", "guardian"):
        for method, path, data in (
            ("PATCH", f"/sections/{section}", {"description": "Inválido"}),
            ("DELETE", f"/sections/{section}", None),
            ("PATCH", f"/enrollments/{a['enrollment_id']}", {"state": "withdrawn"}),
            ("DELETE", f"/enrollments/{a['enrollment_id']}", None),
            (
                "POST",
                "/enrollments/",
                {"student_id": students[1], "section_id": section, "period": "2026-2027"},
            ),
        ):
            response = client.request(method, path, headers=tokens[profile], json=data)
            assert response.status_code == 403, response.text
    with sessions() as db:
        assert db.get(Enrollment, a["enrollment_id"]).state == "enrolled"
        assert db.get(Section, section).description == "Un cupo"


def test_section_capacity_and_period_cannot_invalidate_existing_selections(institution):
    client, _, section, students, tokens = institution
    assert (
        client.patch(
            f"/sections/{section}", headers=tokens["admin"], json={"capacity": 2}
        ).status_code
        == 200
    )
    select(institution, students[0])
    select(institution, students[1])
    for changes in ({"capacity": 1}, {"period_name": "MISSING"}, {"period_name": ""}):
        response = client.patch(f"/sections/{section}", headers=tokens["admin"], json=changes)
        assert response.status_code == 409, response.text


def test_delete_releases_only_one_seat_and_promotes_once(institution):
    client, sessions, section, students, tokens = institution
    a, b, c = [select(institution, s) for s in students[:3]]
    assert (
        client.delete(f"/enrollments/{a['enrollment_id']}", headers=tokens["admin"]).status_code
        == 200
    )
    assert (
        client.delete(f"/enrollments/{a['enrollment_id']}", headers=tokens["admin"]).status_code
        == 404
    )
    with sessions() as db:
        assert db.get(Enrollment, b["enrollment_id"]).state == "enrolled"
        assert db.get(Enrollment, c["enrollment_id"]).state == "waitlisted"
        assert db.query(Enrollment).filter_by(section_id=section, state="enrolled").count() == 1


def test_teacher_history_profile_and_documents_have_consistent_scope(institution):
    client, sessions, section, _, tokens = institution
    with sessions() as db:
        student = db.query(Student).filter_by(enrollment_number="DEMO-2026-001").one()
        student_id = student.student_id
        other_teacher = Teacher(
            first_name="Fuera",
            last_name="Ámbito",
            email="scope@example.com",
            specialty="Prueba",
            telephone="123",
            address="Ficticia",
        )
        db.add(other_teacher)
        db.flush()
        foreign = db.query(Section).filter_by(code="MAT-101-B").one()
        foreign.teacher_id = other_teacher.teacher_id
        foreign_id = foreign.section_id
        forbidden_grades = {g.grade_id for e in foreign.enrollments for g in e.grades}
        db.commit()
    headers = tokens["docente"]
    history = client.get(f"/academic/students/{student_id}/grades", headers=headers)
    assert history.status_code == 200
    assert history.json()
    assert not forbidden_grades.intersection(item["grade_id"] for item in history.json())
    for suffix in ("profile", "schedule", "attendance-summary"):
        response = client.get(f"/academic/students/{student_id}/{suffix}", headers=headers)
        assert response.status_code == 200, response.text
        items = response.json()["enrollments"] if suffix == "profile" else response.json()
        assert all(item["section_id"] != foreign_id for item in items)
    for path in (
        f"/records/students/{student_id}/transcript",
        f"/curriculum/students/{student_id}/progress",
        f"/governance/students/{student_id}/graduation-audit",
        *[
            f"/documents/students/{student_id}/{name}.pdf"
            for name in ("transcript", "report-card", "enrollment-certificate")
        ],
    ):
        assert client.get(path, headers=headers).status_code == 403, path
        assert client.get(path, headers=tokens["admin"]).status_code == 200, path
        assert client.get(path, headers=tokens["estudiante"]).status_code == 200, path


def test_seed_institution_respects_capacity_and_teacher_grants(institution):
    from scripts.seed_institution import seed_institution

    _, sessions, _, _, _ = institution
    with sessions() as db:
        seed_institution(db)
        for section in db.query(Section):
            assert sum(e.state == "enrolled" for e in section.enrollments) <= section.capacity
        teacher = db.query(Role).filter_by(name="teacher").one()
        grants = {
            row[0]
            for row in db.query(Permission.slug)
            .join(RolePermission)
            .filter(RolePermission.role_id == teacher.role_id)
        }
        assert "academic.manage" not in grants


@pytest.mark.skipif(TEST_DATABASE_URL is not None, reason="Copia de seguridad del archivo SQLite")
def test_demo_capacity_repair_is_backed_up_preserves_records_and_is_idempotent(institution):
    from pathlib import Path

    from scripts.repair_demo_capacity import repair
    from scripts.seed_institution import seed_institution

    _, sessions, _, _, _ = institution
    with sessions() as db:
        seed_institution(db)
        db.query(Section).filter(Section.code.in_(["DS-101-A", "AC-101-A", "MD-101-A"])).update(
            {"capacity": 30}
        )
        db.commit()
        database = Path(db.get_bind().url.database)
    plan = repair(database)
    assert len(plan["sections"]) == 3
    assert not plan["applied"]
    result = repair(database, apply=True)
    assert result["applied"]
    assert Path(result["backup"]).is_file()
    assert result["preserved_counts"]["students"] == 120
    assert result["preserved_counts"]["enrollments"] == 360
    assert not repair(database, apply=True)["sections"]
