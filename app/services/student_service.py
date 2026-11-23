from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.configuration_model import InstitutionSettings
from app.repositories.student_repository import (
    create_student,
    delete_student,
    get_student_by_id,
    get_students,
    update_student,
)
from app.schemas.student_schema import StudentCreate, StudentUpdate
from app.services.audit_log import changes, record, snapshot
from app.services.business_time import business_date

# Fields whose change is recorded on PATCH /students (holds and status first).
AUDITED_FIELDS = (
    "academic_hold",
    "financial_hold",
    "active",
    "first_name",
    "last_name",
    "email",
    "telephone",
    "address",
    "document_number",
    "enrollment_number",
)


def create_student_service(
    db: Session, student_data: StudentCreate, actor=None, commit: bool = True
):
    """Create a student. With ``commit=False`` the caller records and commits."""
    from app.services.governance_workflow import lock_governance

    lock_governance(db)
    students = get_students(db)

    for student in students:
        if student.email == student_data.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Ya existe ese correo electrónico"
            )

    if not student_data.enrollment_number:
        settings = db.get(InstitutionSettings, 1)
        if settings is None:
            settings = InstitutionSettings(settings_id=1)
            db.add(settings)
            db.flush()
        year = business_date().year
        sequence = str(settings.next_enrollment_number).zfill(settings.enrollment_digits)
        generated = f"{settings.enrollment_prefix}-{year}-{sequence}"
        from app.models.student_model import Student

        while db.query(Student).filter_by(enrollment_number=generated).first():
            settings.next_enrollment_number += 1
            sequence = str(settings.next_enrollment_number).zfill(settings.enrollment_digits)
            generated = f"{settings.enrollment_prefix}-{year}-{sequence}"
        settings.next_enrollment_number += 1
        student_data = student_data.model_copy(update={"enrollment_number": generated})
    student = create_student(db, student_data)
    if commit:
        record(
            db,
            actor,
            "student.created",
            f"student:{student.student_id}",
            f"{student.enrollment_number} {student.first_name} {student.last_name}",
        )
        db.commit()
        db.refresh(student)
    return student


def get_students_service(db: Session):
    return get_students(db)


def get_student_by_id_service(db: Session, student_id: int):

    student = get_student_by_id(db, student_id)

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Estudiante no encontrado"
        )

    return student


def update_student_service(db: Session, student_id: int, student_data: StudentUpdate, actor):
    current = get_student_by_id_service(db, student_id)
    before = snapshot(current, AUDITED_FIELDS)
    if "career_id" in student_data.model_fields_set and student_data.career_id != current.career_id:
        raise HTTPException(
            409,
            f"El estudiante {student_id} requiere un traslado de carrera. Registra el motivo en el flujo de traslado",
        )

    held = current.financial_hold
    student = update_student(db, student_id, student_data)

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Estudiante no encontrado"
        )
    if student.financial_hold != held:
        # A hold set or removed by a person is manual: the daily job never lifts it.
        student.financial_hold_source = "manual" if student.financial_hold else None

    record(
        db,
        actor,
        "student.updated",
        f"student:{student_id}",
        changes(before, snapshot(student, AUDITED_FIELDS)),
    )
    db.commit()
    db.refresh(student)
    return student


def delete_student_service(db: Session, student_id: int, actor):
    student = delete_student(db, student_id)

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Estudiante no encontrado"
        )

    record(db, actor, "student.deactivated", f"student:{student_id}", student.enrollment_number)
    db.commit()
    return {"message": "Estudiante eliminado"}
