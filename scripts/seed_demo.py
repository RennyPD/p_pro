"""Carga datos de demostración reproducibles sin duplicar registros."""

from datetime import datetime, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models import (
    Attendance,
    Career,
    Enrollment,
    Grade,
    Role,
    Section,
    Student,
    Subject,
    Teacher,
    User,
)
from app.security import hash_password

DEMO_PASSWORDS = {
    "demo.admin": "NexoAdmin2026!",
    "demo.docente": "NexoDocente2026!",
    "demo.estudiante": "NexoEstudiante2026!",
}


def _one_or_create(db: Session, model, defaults: dict, **criteria):
    instance = db.scalar(select(model).filter_by(**criteria))
    if instance is None:
        instance = model(**criteria, **defaults)
        db.add(instance)
        db.flush()
    return instance


def seed_demo(db: Session) -> dict[str, int]:
    """Crea un escenario académico mínimo y puede ejecutarse más de una vez."""
    try:
        roles = {
            name: _one_or_create(db, Role, {"description": description}, name=name)
            for name, description in {
                "admin": "Administración completa de la plataforma",
                "teacher": "Gestión docente de notas y asistencia",
                "student": "Consulta del expediente académico propio",
            }.items()
        }
        career = _one_or_create(
            db,
            Career,
            {"description": "Programa demostrativo para validar el flujo académico"},
            name="Ingeniería de Software",
        )
        teacher = _one_or_create(
            db,
            Teacher,
            {
                "first_name": "Elena",
                "last_name": "Martínez",
                "specialty": "Desarrollo de software",
                "telephone": "809-555-0101",
                "address": "Santo Domingo",
                "active": True,
            },
            email="elena.demo@nexo.local",
        )
        student = _one_or_create(
            db,
            Student,
            {
                "first_name": "Daniel",
                "last_name": "Santos",
                "email": "daniel.demo@nexo.local",
                "telephone": "809-555-0102",
                "address": "Santo Domingo",
                "active": True,
                "career_id": career.career_id,
            },
            enrollment_number="DEMO-2026-001",
        )
        subjects = {
            code: _one_or_create(db, Subject, {"description": description}, code=code)
            for code, description in {
                "PROG-101": "Fundamentos de programación",
                "MAT-101": "Matemática discreta",
            }.items()
        }
        section_specs = [
            (
                "PROG-101-A",
                "Programación · Sección A",
                subjects["PROG-101"],
                "Lunes, Miércoles",
                time(8),
                time(9, 30),
            ),
            (
                "MAT-101-B",
                "Matemática · Sección B",
                subjects["MAT-101"],
                "Martes, Jueves",
                time(10),
                time(11, 30),
            ),
        ]
        sections = []
        for code, description, subject, days, start, end in section_specs:
            sections.append(
                _one_or_create(
                    db,
                    Section,
                    {
                        "description": description,
                        "teacher_id": teacher.teacher_id,
                        "subject_id": subject.subject_id,
                        "days_of_week": days,
                        "start_time": start,
                        "end_time": end,
                    },
                    code=code,
                )
            )
        enrollments = [
            _one_or_create(
                db,
                Enrollment,
                {"state": "enrolled"},
                student_id=student.student_id,
                section_id=section.section_id,
                period="2026-2027",
            )
            for section in sections
        ]
        _one_or_create(
            db,
            Grade,
            {"grade_value": 92.0, "date_recorded": "2026-09-15"},
            enrollment_id=enrollments[0].enrollment_id,
            grade_type="Práctica inicial",
        )
        _one_or_create(
            db,
            Attendance,
            {"present": True},
            enrollment_id=enrollments[0].enrollment_id,
            date=datetime(2026, 9, 15, 8, 0),
        )
        user_specs = [
            ("demo.admin", "admin.demo@nexo.local", roles["admin"], None, None),
            ("demo.docente", "elena.demo@nexo.local", roles["teacher"], None, teacher.teacher_id),
            (
                "demo.estudiante",
                "daniel.demo@nexo.local",
                roles["student"],
                student.student_id,
                None,
            ),
        ]
        for username, email, role, student_id, teacher_id in user_specs:
            _one_or_create(
                db,
                User,
                {
                    "email": email,
                    "password": hash_password(DEMO_PASSWORDS[username]),
                    "role_id": role.role_id,
                    "student_id": student_id,
                    "teacher_id": teacher_id,
                },
                username=username,
            )
        db.commit()
        return {
            "roles": len(roles),
            "subjects": len(subjects),
            "sections": len(sections),
            "enrollments": len(enrollments),
            "users": len(user_specs),
        }
    except Exception:
        db.rollback()
        raise


def main() -> None:
    with SessionLocal() as db:
        summary = seed_demo(db)
    print("Datos demo listos:", ", ".join(f"{key}={value}" for key, value in summary.items()))


if __name__ == "__main__":
    main()
