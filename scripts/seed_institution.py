"""Reemplaza los datos actuales por una institución ficticia completa."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from random import Random

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models import (
    AcademicPeriod,
    Attendance,
    AuditLog,
    Career,
    Charge,
    CurriculumCourse,
    Enrollment,
    Grade,
    InstitutionSettings,
    Payment,
    RefreshToken,
    Role,
    Section,
    Student,
    StudentAccount,
    Subject,
    Teacher,
    User,
)
from app.security import hash_password

PASSWORDS = {
    "admin": "NexoAdmin2026!",
    "teacher": "NexoDocente2026!",
    "student": "NexoEstudiante2026!",
}

CAREER_SPECS = [
    (
        "Desarrollo de Software",
        "Formación técnica en programación, datos y construcción de aplicaciones.",
        [
            ("DS-101", "Fundamentos de Programación", 4),
            ("DS-102", "Lógica y Algoritmos", 4),
            ("DS-201", "Bases de Datos", 4),
            ("DS-202", "Desarrollo Web", 4),
            ("DS-301", "Ingeniería de Software", 3),
        ],
    ),
    (
        "Administración y Contabilidad",
        "Gestión administrativa, financiera y contable para organizaciones.",
        [
            ("AC-101", "Contabilidad Básica", 4),
            ("AC-102", "Matemática Financiera", 3),
            ("AC-201", "Costos y Presupuestos", 4),
            ("AC-202", "Gestión Administrativa", 3),
            ("AC-301", "Auditoría", 4),
        ],
    ),
    (
        "Mercadeo Digital",
        "Estrategia, comunicación y analítica para medios digitales.",
        [
            ("MD-101", "Fundamentos de Mercadeo", 3),
            ("MD-102", "Comunicación Digital", 3),
            ("MD-201", "Contenido y Redes Sociales", 4),
            ("MD-202", "Analítica Digital", 4),
            ("MD-301", "Estrategia de Campañas", 4),
        ],
    ),
]

TEACHER_SPECS = [
    ("Ana", "Rodríguez", "Programación y algoritmos"),
    ("Carlos", "Méndez", "Bases de datos y desarrollo web"),
    ("Lucía", "Fernández", "Contabilidad y finanzas"),
    ("Javier", "Castillo", "Administración y auditoría"),
    ("María", "Reyes", "Comunicación y contenidos"),
    ("Andrés", "Peña", "Analítica y estrategia digital"),
]

FIRST_NAMES = [
    "Sofía",
    "Mateo",
    "Valentina",
    "Sebastián",
    "Camila",
    "Samuel",
    "Isabella",
    "Daniel",
    "Gabriela",
    "David",
    "Emma",
    "Gabriel",
    "Victoria",
    "Adrián",
    "Natalia",
    "Alejandro",
    "Paula",
    "Diego",
    "Mariana",
    "Nicolás",
    "Carolina",
    "Luis",
    "Laura",
    "José",
    "Amanda",
    "Emilio",
    "Sara",
    "Ángel",
    "Elena",
    "Marco",
    "Claudia",
    "Tomás",
    "Patricia",
    "Bruno",
    "Diana",
    "Iván",
]

LAST_NAMES = [
    "García",
    "Martínez",
    "López",
    "Santos",
    "Pérez",
    "Ramírez",
    "Torres",
    "Díaz",
    "Vargas",
    "Morales",
    "Ortiz",
    "Herrera",
]


def clear_application_data(db: Session) -> None:
    """Vacía las tablas en un orden que respeta todas las llaves foráneas."""
    for model in (
        RefreshToken,
        AuditLog,
        Payment,
        Charge,
        StudentAccount,
        Attendance,
        Grade,
        Enrollment,
        User,
        CurriculumCourse,
        Section,
        Student,
        Teacher,
        Subject,
        AcademicPeriod,
        InstitutionSettings,
        Career,
        Role,
    ):
        db.execute(delete(model))
    db.flush()


def seed_institution(db: Session) -> dict[str, int]:
    rng = Random(20260918)
    clear_application_data(db)

    roles = {
        name: Role(name=name, description=description)
        for name, description in {
            "admin": "Administración completa de la institución",
            "teacher": "Gestión de secciones, calificaciones y asistencia",
            "student": "Consulta del expediente académico personal",
        }.items()
    }
    db.add_all(roles.values())
    db.add(
        InstitutionSettings(
            settings_id=1,
            institution_name="Instituto Técnico Horizonte",
            enrollment_prefix="ITH",
            enrollment_digits=5,
            next_enrollment_number=37,
            passing_grade=70,
        )
    )
    db.add_all(
        [
            AcademicPeriod(
                name="2025-2026", start_date=date(2025, 8, 18), end_date=date(2026, 6, 26)
            ),
            AcademicPeriod(
                name="2026-2027",
                start_date=date(2026, 8, 17),
                end_date=date(2027, 6, 25),
                active=True,
            ),
        ]
    )

    careers: list[Career] = []
    subjects_by_career: list[list[Subject]] = []
    for career_name, description, subject_specs in CAREER_SPECS:
        career = Career(name=career_name, description=description)
        subjects = [Subject(code=code, description=name) for code, name, _ in subject_specs]
        db.add(career)
        db.add_all(subjects)
        db.flush()
        careers.append(career)
        subjects_by_career.append(subjects)
        previous_subject = None
        for term, (subject, (_, _, credits)) in enumerate(zip(subjects, subject_specs), start=1):
            db.add(
                CurriculumCourse(
                    career_id=career.career_id,
                    subject_id=subject.subject_id,
                    term_number=term,
                    credits=credits,
                    prerequisite_subject_id=previous_subject.subject_id
                    if previous_subject
                    else None,
                )
            )
            previous_subject = subject

    teachers = []
    for index, (first_name, last_name, specialty) in enumerate(TEACHER_SPECS, start=1):
        teacher = Teacher(
            first_name=first_name,
            last_name=last_name,
            specialty=specialty,
            email=f"docente{index:02d}@horizonte.example",
            telephone=f"809-555-11{index:02d}",
            address="Santo Domingo, República Dominicana",
            active=True,
        )
        db.add(teacher)
        teachers.append(teacher)
    db.flush()

    day_pairs = ["Lunes, Miércoles", "Martes, Jueves", "Viernes"]
    start_times = [time(8), time(10), time(13), time(15), time(17)]
    sections_by_career: list[list[Section]] = []
    all_sections = []
    for career_index, subjects in enumerate(subjects_by_career):
        career_sections = []
        for subject_index, subject in enumerate(subjects):
            teacher = teachers[(career_index * 2 + subject_index) % len(teachers)]
            start = start_times[subject_index]
            section = Section(
                code=f"{subject.code}-A",
                description=f"{subject.description} · Grupo A",
                teacher_id=teacher.teacher_id,
                subject_id=subject.subject_id,
                days_of_week=day_pairs[subject_index % len(day_pairs)],
                start_time=start,
                end_time=time(start.hour + 1, 30),
            )
            db.add(section)
            career_sections.append(section)
            all_sections.append(section)
        sections_by_career.append(career_sections)
    db.flush()

    students = []
    enrollments = []
    grade_count = 0
    attendance_count = 0
    charge_count = 0
    payment_count = 0
    today = date(2026, 9, 18)
    for index, first_name in enumerate(FIRST_NAMES, start=1):
        career_index = (index - 1) // 12
        last_name = LAST_NAMES[(index - 1) % len(LAST_NAMES)]
        student = Student(
            first_name=first_name,
            last_name=last_name,
            email=f"estudiante{index:03d}@horizonte.example",
            enrollment_number=f"ITH-2026-{index:05d}",
            telephone=f"809-555-{2000 + index}",
            address=f"Sector académico {1 + index % 8}, Santo Domingo",
            active=True,
            career_id=careers[career_index].career_id,
        )
        db.add(student)
        db.flush()
        students.append(student)

        for course_index, section in enumerate(sections_by_career[career_index][:3]):
            enrollment = Enrollment(
                student_id=student.student_id,
                section_id=section.section_id,
                period="2026-2027",
                state="enrolled",
            )
            db.add(enrollment)
            db.flush()
            enrollments.append(enrollment)
            for grade_type, offset in (("Práctica", 0), ("Parcial", 3)):
                score = min(100, 68 + (index * 3 + course_index * 5 + offset) % 30)
                db.add(
                    Grade(
                        enrollment_id=enrollment.enrollment_id,
                        grade_value=score,
                        grade_type=grade_type,
                        date_recorded=f"2026-09-{10 + course_index:02d}",
                    )
                )
                grade_count += 1
            for session_index in range(6):
                db.add(
                    Attendance(
                        enrollment_id=enrollment.enrollment_id,
                        date=datetime(2026, 9, 1 + session_index * 2, 8 + course_index),
                        present=rng.random() > 0.12,
                    )
                )
                attendance_count += 1

        account = StudentAccount(
            student_id=student.student_id,
            cutoff_day=15 if index % 2 else 20,
            due_day=25 if index % 2 else 30,
        )
        db.add(account)
        db.flush()
        tuition = 4200 + career_index * 500
        db.add_all(
            [
                Charge(
                    student_account_id=account.student_account_id,
                    description="Mensualidad de septiembre",
                    amount=tuition,
                    due_date=today - timedelta(days=3),
                ),
                Charge(
                    student_account_id=account.student_account_id,
                    description="Materiales académicos",
                    amount=850,
                    due_date=today + timedelta(days=12),
                ),
            ]
        )
        charge_count += 2
        if index % 4 != 0:
            db.add(
                Payment(
                    student_account_id=account.student_account_id,
                    amount=2000 + (index % 3) * 500,
                    reference=f"REC-2026-{index:04d}",
                    note="Abono de mensualidad",
                    paid_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=index % 7),
                )
            )
            payment_count += 1

    db.flush()
    users = [
        User(
            username="admin.horizonte",
            email="administracion@horizonte.example",
            password=hash_password(PASSWORDS["admin"]),
            role_id=roles["admin"].role_id,
        )
    ]
    users.extend(
        User(
            username=f"profesor.{index:02d}",
            email=teacher.email,
            password=hash_password(PASSWORDS["teacher"]),
            role_id=roles["teacher"].role_id,
            teacher_id=teacher.teacher_id,
        )
        for index, teacher in enumerate(teachers, start=1)
    )
    users.extend(
        User(
            username=f"estudiante.{index:03d}",
            email=student.email,
            password=hash_password(PASSWORDS["student"]),
            role_id=roles["student"].role_id,
            student_id=student.student_id,
        )
        for index, student in enumerate(students, start=1)
    )
    db.add_all(users)
    db.commit()
    return {
        "careers": len(careers),
        "subjects": sum(map(len, subjects_by_career)),
        "teachers": len(teachers),
        "students": len(students),
        "sections": len(all_sections),
        "enrollments": len(enrollments),
        "grades": grade_count,
        "attendances": attendance_count,
        "charges": charge_count,
        "payments": payment_count,
        "users": len(users),
    }


def main() -> None:
    with SessionLocal() as db:
        try:
            summary = seed_institution(db)
        except Exception:
            db.rollback()
            raise
    print(
        "Institución ficticia lista:", ", ".join(f"{key}={value}" for key, value in summary.items())
    )


if __name__ == "__main__":
    main()
