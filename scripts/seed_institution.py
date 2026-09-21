"""Reemplaza los datos actuales por una institución ficticia completa."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from random import Random

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models import (
    AcademicPeriod,
    AdmissionApplication,
    Announcement,
    ApprovalRequest,
    Assessment,
    Assignment,
    Attendance,
    AuditLog,
    BillingConcept,
    CalendarEvent,
    Career,
    CashClosing,
    Charge,
    Classroom,
    CourseEquivalence,
    CurriculumCourse,
    EarlyAlert,
    Enrollment,
    FinancialAdjustment,
    Grade,
    Guardian,
    Installment,
    InstitutionSettings,
    LessonPlan,
    Notification,
    Payment,
    PaymentPlan,
    Permission,
    RefreshToken,
    Role,
    RolePermission,
    Section,
    SectionMeeting,
    Student,
    StudentAccount,
    StudentCareerHistory,
    StudentDocument,
    StudentGuardian,
    Subject,
    Submission,
    Teacher,
    User,
)
from app.security import hash_password

PASSWORDS = {
    "admin": "NexoAdmin2026!",
    "teacher": "NexoDocente2026!",
    "student": "NexoEstudiante2026!",
    "guardian": "NexoTutor2026!",
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
        CashClosing,
        BillingConcept,
        RolePermission,
        Permission,
        StudentDocument,
        StudentCareerHistory,
        CourseEquivalence,
        ApprovalRequest,
        Submission,
        Assignment,
        LessonPlan,
        CalendarEvent,
        EarlyAlert,
        AdmissionApplication,
        RefreshToken,
        AuditLog,
        Notification,
        Announcement,
        Payment,
        Installment,
        PaymentPlan,
        FinancialAdjustment,
        Charge,
        StudentAccount,
        Attendance,
        Grade,
        Assessment,
        Enrollment,
        User,
        StudentGuardian,
        Guardian,
        CurriculumCourse,
        SectionMeeting,
        Section,
        Student,
        Teacher,
        Subject,
        Classroom,
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
            "guardian": "Consulta de estudiantes vinculados como tutor",
        }.items()
    }
    db.add_all(roles.values())
    db.flush()
    permission_specs = {
        "academic.manage": "Gestionar operación académica",
        "grades.manage": "Registrar y cerrar calificaciones",
        "finance.manage": "Gestionar cuentas y caja",
        "reports.view": "Consultar reportes institucionales",
        "records.own": "Consultar expediente vinculado",
        "communications.manage": "Publicar comunicaciones",
    }
    permissions = {
        slug: Permission(slug=slug, description=description)
        for slug, description in permission_specs.items()
    }
    db.add_all(permissions.values())
    db.flush()
    grants = {
        "admin": set(permissions),
        "teacher": {"academic.manage", "grades.manage", "communications.manage"},
        "student": {"records.own"},
        "guardian": {"records.own"},
    }
    db.add_all(
        RolePermission(role_id=roles[role].role_id, permission_id=permissions[slug].permission_id)
        for role, slugs in grants.items()
        for slug in slugs
    )
    db.add(
        InstitutionSettings(
            settings_id=1,
            institution_name="Instituto Técnico Horizonte",
            enrollment_prefix="ITH",
            enrollment_digits=5,
            next_enrollment_number=121,
            passing_grade=70,
        )
    )
    db.add_all(
        [
            AcademicPeriod(
                name="2025-2026", start_date=date(2025, 8, 18), end_date=date(2026, 6, 26),
                status="closed", period_type="quadrimester", sequence=3,
                academic_year="2025-2026",
            ),
            AcademicPeriod(
                name="2026-2027",
                start_date=date(2026, 8, 17),
                end_date=date(2027, 6, 25),
                active=True,
                status="active",
                period_type="quadrimester",
                sequence=1,
                academic_year="2026-2027",
                registration_start=date(2026, 7, 15),
                registration_end=date(2026, 10, 15),
                withdrawal_deadline=date(2026, 10, 30),
                grading_deadline=date(2027, 6, 30),
            ),
        ]
    )

    careers: list[Career] = []
    subjects_by_career: list[list[Subject]] = []
    for career_index, (career_name, description, subject_specs) in enumerate(CAREER_SPECS, start=1):
        career = Career(
            code=f"ITH-{career_index:02d}",
            name=career_name,
            description=description,
            academic_level="undergraduate",
            degree_title=f"Licenciado en {career_name}",
            term_type="quadrimester",
            duration_terms=9,
            required_credits=sum(item[2] for item in subject_specs),
            curriculum_version="2026",
        )
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
                    course_type="capstone" if term == len(subject_specs) else "required",
                    curriculum_version="2026",
                )
            )
            previous_subject = subject

    for career, subjects in zip(careers, subjects_by_career):
        db.add(
            CourseEquivalence(
                career_id=career.career_id,
                source_subject_id=subjects[0].subject_id,
                target_subject_id=subjects[1].subject_id,
                curriculum_version="2026",
                notes="Equivalencia ficticia para validar reconocimiento curricular.",
            )
        )

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

    classrooms = [
        Classroom(name=f"Aula {name}", capacity=32, location=f"Edificio {building}")
        for name, building in (("A-101", "A"), ("A-202", "A"), ("B-103", "B"), ("LAB-1", "Tecnología"))
    ]
    db.add_all(classrooms)
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
                capacity=30,
                minimum_capacity=8,
                room=classrooms[subject_index % len(classrooms)].name,
                modality=("hybrid" if subject_index == 3 else "in_person"),
                status="active",
                period_name="2026-2027",
            )
            db.add(section)
            career_sections.append(section)
            all_sections.append(section)
        sections_by_career.append(career_sections)
    db.flush()

    assessments_by_section: dict[int, list[Assessment]] = {}
    for index, section in enumerate(all_sections):
        components = [
            Assessment(section_id=section.section_id, name="Proyecto aplicado", weight=40, due_date=date(2026, 10, 20)),
            Assessment(section_id=section.section_id, name="Examen final", weight=60, due_date=date(2026, 11, 25)),
        ]
        db.add_all(components)
        assessments_by_section[section.section_id] = components
        classroom = classrooms[index % len(classrooms)]
        for day in section.days_of_week.split(", "):
            db.add(SectionMeeting(section_id=section.section_id, classroom_id=classroom.classroom_id, day_of_week=day, start_time=section.start_time, end_time=section.end_time, modality=section.modality, virtual_url="https://meet.example/aula" if section.modality == "hybrid" else ""))
    db.flush()

    students = []
    enrollments = []
    grade_count = 0
    attendance_count = 0
    charge_count = 0
    payment_count = 0
    today = date(2026, 9, 18)
    for index in range(1, 121):
        first_name = FIRST_NAMES[(index - 1) % len(FIRST_NAMES)]
        career_index = (index - 1) % len(careers)
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
            for assessment, offset in zip(assessments_by_section[section.section_id], (0, 3)):
                score = min(100, 68 + (index * 3 + course_index * 5 + offset) % 30)
                db.add(
                    Grade(
                        enrollment_id=enrollment.enrollment_id,
                        grade_value=score,
                        assessment_id=assessment.assessment_id,
                        grade_type=assessment.name,
                        date_recorded=f"2026-09-{10 + course_index:02d}",
                    )
                )
                grade_count += 1
            for session_index in range(6):
                is_present = rng.random() > 0.12
                db.add(
                    Attendance(
                        enrollment_id=enrollment.enrollment_id,
                        date=datetime(2026, 9, 1 + session_index * 2, 8 + course_index),
                        present=is_present,
                        status="present" if is_present else "absent",
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
    guardians = []
    for index, student in enumerate(students[:12], start=1):
        guardian = Guardian(
            first_name=f"Tutor {index}",
            last_name=student.last_name,
            email=f"tutor{index:02d}@horizonte.example",
            telephone=f"809-555-30{index:02d}",
            address=student.address,
        )
        db.add(guardian)
        db.flush()
        guardians.append(guardian)
        db.add(
            StudentGuardian(
                student_id=student.student_id,
                guardian_id=guardian.guardian_id,
                relationship="tutor",
                primary_contact=True,
                emergency_contact=True,
                authorized_pickup=True,
            )
        )
        users.append(
            User(
                username=f"tutor.{index:02d}",
                email=guardian.email,
                password=hash_password(PASSWORDS["guardian"]),
                role_id=roles["guardian"].role_id,
                guardian_id=guardian.guardian_id,
            )
        )
    db.add_all(users)
    db.flush()

    admin_user = users[0]
    db.add_all(
        [
            CalendarEvent(title="Bienvenida institucional", description="Apertura del período académico", event_type="activity", audience="all", starts_at=datetime(2026, 9, 22, 9), ends_at=datetime(2026, 9, 22, 11), created_by=admin_user.user_id),
            CalendarEvent(title="Semana de parciales", description="Evaluaciones del primer corte", event_type="exam", audience="all", starts_at=datetime(2026, 10, 19, 8), ends_at=datetime(2026, 10, 23, 18), created_by=admin_user.user_id),
            CalendarEvent(title="Fecha límite de retiro", description="Cierre de retiros académicos", event_type="deadline", audience="student", starts_at=datetime(2026, 10, 30, 8), ends_at=datetime(2026, 10, 30, 18), created_by=admin_user.user_id),
        ]
    )
    for index, section in enumerate(all_sections[:8]):
        teacher_id = section.teacher_id
        db.add(LessonPlan(section_id=section.section_id, teacher_id=teacher_id, scheduled_date=date(2026, 9, 21) + timedelta(days=index), title=f"Unidad {index + 1}: aplicación práctica", content="Objetivos, demostración guiada y ejercicio colaborativo.", competencies="Análisis, comunicación y resolución de problemas", status="planned" if index % 3 else "delivered"))
        assignment = Assignment(section_id=section.section_id, title=f"Actividad práctica {index + 1}", instructions="Desarrolla el caso y presenta conclusiones justificadas.", due_at=datetime(2026, 10, 5 + index, 23, 59), max_score=100, assessment_id=assessments_by_section[section.section_id][0].assessment_id, created_by=admin_user.user_id, published=True)
        db.add(assignment)
        db.flush()
        for enrollment in section.enrollments[:4]:
            db.add(Submission(assignment_id=assignment.assignment_id, student_id=enrollment.student_id, content="Entrega ficticia completa para validación funcional.", status="graded" if enrollment.student_id % 2 else "submitted", score=85 if enrollment.student_id % 2 else None, feedback="Buen desarrollo y argumentación." if enrollment.student_id % 2 else ""))

    for index, student in enumerate(students[:10]):
        db.add(EarlyAlert(student_id=student.student_id, category=("attendance" if index % 2 else "academic"), severity=("high" if index < 3 else "medium"), reason=("Asistencia acumulada inferior al objetivo institucional" if index % 2 else "Rendimiento por debajo de la meta del período"), status="resolved" if index == 9 else "open", created_by=admin_user.user_id))

    admission_states = ["submitted", "review", "accepted", "rejected"]
    for index in range(12):
        db.add(AdmissionApplication(first_name=f"Aspirante {index + 1}", last_name=LAST_NAMES[index % len(LAST_NAMES)], email=f"aspirante{index + 1:02d}@horizonte.example", telephone=f"809-555-40{index + 1:02d}", career_id=careers[index % len(careers)].career_id, status=admission_states[index % len(admission_states)], checklist="Identificación: recibida; Certificado: pendiente" if index % 2 else "Expediente completo", notes="Caso ficticio para validación del flujo de admisiones."))

    db.add_all([
        ApprovalRequest(request_type="grade_change", resource_type="grade", resource_id=1, reason="Corrección documentada de calificación", status="pending", requested_by=users[1].user_id),
        ApprovalRequest(request_type="attendance_change", resource_type="attendance", resource_id=1, reason="Justificación médica recibida", status="pending", requested_by=users[2].user_id),
    ])
    db.add_all([
        Announcement(title="Inicio del período", body="Consulta tu horario y confirma tus asignaturas.", audience="all", created_by=admin_user.user_id),
        Announcement(title="Recordatorio de evaluaciones", body="Revisa las fechas publicadas en tu agenda.", audience="student", created_by=admin_user.user_id),
    ])
    for user in users[:15]:
        db.add(Notification(user_id=user.user_id, title="Bienvenido a Nexo", body="Tu espacio institucional está listo.", category="general"))
    db.add_all([
        BillingConcept(name="Matrícula por período", description="Cargo académico ordinario", amount=4200, frequency="term"),
        BillingConcept(name="Laboratorio", description="Uso de espacios especializados", amount=850, frequency="term"),
        BillingConcept(name="Carné estudiantil", description="Emisión o renovación", amount=350, frequency="annual"),
    ])
    for student in students[:6]:
        db.add(StudentDocument(student_id=student.student_id, document_type="identification", filename=f"identificacion-{student.enrollment_number}.pdf", mime_type="application/pdf", content=b"%PDF-1.4\n% escenario ficticio\n", uploaded_by=admin_user.user_id))
    db.add(AuditLog(user_id=admin_user.user_id, action="institution.seeded", resource="demo_data", detail="Escenario institucional integral generado", created_at=datetime.now(UTC).replace(tzinfo=None)))
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
        "assessments": len(all_sections) * 2,
        "calendar_events": 3,
        "assignments": 8,
        "alerts": 10,
        "admissions": 12,
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
