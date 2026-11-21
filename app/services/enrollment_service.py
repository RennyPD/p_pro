from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.attendance_model import AttendanceChange
from app.models.configuration_model import InstitutionSettings
from app.models.curriculum_model import CurriculumCourse
from app.models.enrollment_model import Enrollment
from app.models.operations_model import Assignment, Submission
from app.models.section_model import Section
from app.models.student_model import Student
from app.repositories.enrollment_repository import (
    create_enrollment,
    delete_enrollment,
    get_enrollment_by_id,
    get_enrollments,
    update_enrollment,
)
from app.schemas.enrollment_schema import EnrollmentCreate, EnrollmentUpdate
from app.services.academic_recognition import recognize
from app.services.audit_log import changes, record, snapshot
from app.services.business_time import business_date
from app.services.effective_schedule import effective_blocks, overlap
from app.services.enrollment_policy import selection_period
from app.services.governance_workflow import lock_governance

AUDITED_FIELDS = ("state", "waitlist_position")


def describe(enrollment: Enrollment) -> str:
    return (
        f"Estudiante {enrollment.student_id}; sección {enrollment.section_id}; "
        f"período {enrollment.period}; estado {enrollment.state}"
    )


def validate_eligibility(
    db: Session,
    enrollment_data: EnrollmentCreate,
    exclude_id: int | None = None,
    *,
    require_program: bool = False,
    paired_corequisite: int | None = None,
):
    requested_section = db.get(Section, enrollment_data.section_id)
    if requested_section is None:
        raise HTTPException(status_code=404, detail="Sección no encontrada")
    if requested_section.status not in {"published", "active"}:
        raise HTTPException(status_code=409, detail="La sección no está abierta para selección")
    student = db.get(Student, enrollment_data.student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")
    if not student.active:
        raise HTTPException(status_code=409, detail="Un estudiante inactivo no puede inscribirse")
    if student.academic_hold or student.financial_hold:
        reasons = []
        if student.academic_hold:
            reasons.append("académico")
        if student.financial_hold:
            reasons.append("financiero")
        raise HTTPException(
            status_code=409,
            detail=f"El estudiante tiene un bloqueo {' y '.join(reasons)} activo",
        )
    selection_period(db, requested_section.section_id, enrollment_data.period, registration=True)
    recognition = recognize(db, student)
    curriculum_course = (
        db.query(CurriculumCourse)
        .filter(
            CurriculumCourse.career_id == student.career_id,
            CurriculumCourse.subject_id == requested_section.subject_id,
            CurriculumCourse.curriculum_version == student.curriculum_version,
        )
        .first()
    )
    if require_program and curriculum_course is None:
        raise HTTPException(
            409,
            f"La asignatura {requested_section.subject.code} ya no está en tu plan vigente. Retírala del carrito",
        )
    if curriculum_course and curriculum_course.prerequisite_subject_id:
        if curriculum_course.prerequisite_subject_id not in recognition.completed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Falta aprobar el prerrequisito {curriculum_course.prerequisite.code}",
            )
    if curriculum_course and curriculum_course.corequisite_subject_id:
        has_corequisite = any(
            enrollment.period == enrollment_data.period
            and enrollment.state in {"enrolled", "waitlisted"}
            and enrollment.section.subject_id == curriculum_course.corequisite_subject_id
            for enrollment in student.enrollments
        )
        completed_corequisite = curriculum_course.corequisite_subject_id in recognition.completed
        if (
            not has_corequisite
            and not completed_corequisite
            and curriculum_course.corequisite_subject_id != paired_corequisite
        ):
            raise HTTPException(
                status_code=409,
                detail=f"Primero debes seleccionar el correquisito {curriculum_course.corequisite.code}",
            )
    settings = db.get(InstitutionSettings, 1)
    if requested_section.subject_id in recognition.completed:
        raise HTTPException(status_code=409, detail="La asignatura ya fue aprobada")
    current = (
        db.query(Enrollment)
        .filter(
            Enrollment.student_id == enrollment_data.student_id,
            Enrollment.period == enrollment_data.period,
            Enrollment.state.in_(("enrolled", "waitlisted")),
            Enrollment.enrollment_id != exclude_id if exclude_id is not None else True,
        )
        .all()
    )
    same_subject_selection = next(
        (
            enrollment
            for enrollment in current
            if enrollment.section.subject_id == requested_section.subject_id
        ),
        None,
    )
    if same_subject_selection:
        raise HTTPException(
            status_code=409,
            detail=f"La asignatura ya está seleccionada en la sección {same_subject_selection.section.code}",
        )
    max_credits = settings.max_credits_per_period if settings else 24
    current_credits = 0.0
    for enrollment in current:
        if enrollment.curriculum_credits is not None:
            current_credits += enrollment.curriculum_credits
            continue
        course = (
            db.query(CurriculumCourse)
            .filter(
                CurriculumCourse.career_id == student.career_id,
                CurriculumCourse.subject_id == enrollment.section.subject_id,
                CurriculumCourse.curriculum_version == student.curriculum_version,
            )
            .first()
        )
        current_credits += course.credits if course else 0
    requested_credits = curriculum_course.credits if curriculum_course else 0
    if current_credits + requested_credits > max_credits:
        raise HTTPException(status_code=409, detail="Se supera el máximo de créditos permitido")

    requested_slots = effective_blocks(requested_section)
    for enrollment in current:
        if enrollment.state != "enrolled":
            continue
        section = enrollment.section
        if any(
            overlap(slot, other) for slot in requested_slots for other in effective_blocks(section)
        ):
            raise HTTPException(409, f"Choque de horario con la sección {section.code}")
    return requested_section


def occupied_seats(db, section_id, period):
    return (
        db.query(Enrollment)
        .filter_by(section_id=section_id, period=period, state="enrolled")
        .count()
    )


def create_enrollment_service(
    db: Session,
    enrollment_data: EnrollmentCreate,
    *,
    require_program: bool = False,
    paired_corequisite: int | None = None,
    actor=None,
    commit: bool = True,
):
    """Create a selection and record it. With ``commit=False`` the caller commits."""
    # Acquire the database-backed writer lock BEFORE reading eligibility/capacity.
    lock_governance(db)
    if enrollment_data.state != "enrolled" or enrollment_data.waitlist_position is not None:
        raise HTTPException(
            422, "El estado y la posición en la lista de espera los asigna el sistema"
        )
    if (
        db.query(Enrollment)
        .filter_by(
            student_id=enrollment_data.student_id,
            section_id=enrollment_data.section_id,
            period=enrollment_data.period,
        )
        .first()
    ):
        raise HTTPException(409, "Ya existe una selección para este estudiante, sección y período")
    requested_section = validate_eligibility(
        db, enrollment_data, require_program=require_program, paired_corequisite=paired_corequisite
    )
    # Existing eligible waitlisted candidates have priority over newcomers.
    promote_waitlist(db, requested_section.section_id, enrollment_data.period, actor)
    enrolled_count = (
        db.query(Enrollment)
        .filter(
            Enrollment.section_id == requested_section.section_id,
            Enrollment.period == enrollment_data.period,
            Enrollment.state == "enrolled",
        )
        .count()
    )
    if enrolled_count >= requested_section.capacity:
        waiting = (
            db.query(Enrollment)
            .filter(
                Enrollment.section_id == requested_section.section_id,
                Enrollment.period == enrollment_data.period,
                Enrollment.state == "waitlisted",
            )
            .all()
        )
        waitlist_position = max((item.waitlist_position or 0 for item in waiting), default=0) + 1
        enrollment_data = enrollment_data.model_copy(
            update={"state": "waitlisted", "waitlist_position": waitlist_position}
        )
    enrollment = create_enrollment(db, enrollment_data)
    record(
        db,
        actor,
        "enrollment.created",
        f"enrollment:{enrollment.enrollment_id}",
        describe(enrollment),
    )
    if commit:
        db.commit()
        db.refresh(enrollment)
    return enrollment


def get_enrollments_service(db: Session):
    return get_enrollments(db)


def get_enrollment_by_id_service(db: Session, enrollment_id: int):
    enrollment = get_enrollment_by_id(db, enrollment_id)

    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Inscripción no encontrada"
        )

    return enrollment


def update_enrollment_service(
    db: Session, enrollment_id: int, enrollment_data: EnrollmentUpdate, actor=None
):
    lock_governance(db)
    current = get_enrollment_by_id(db, enrollment_id)
    if not current:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Inscripción no encontrada"
        )
    requested = enrollment_data.model_dump(exclude_unset=True)
    for field in ("student_id", "section_id", "period"):
        if field in requested and requested[field] != getattr(current, field):
            raise HTTPException(409, "La selección no se puede cambiar; retírala y crea una nueva")
    if any(
        requested.get(field, getattr(current, field)) is None
        for field in ("student_id", "section_id", "period", "state")
    ):
        raise HTTPException(422, "La identidad y el estado de la selección no pueden quedar vacíos")
    if "waitlist_position" in requested:
        raise HTTPException(422, "La posición en la lista de espera la gestiona el sistema")
    period = selection_period(db, current.section_id, current.period)
    previous_state = current.state
    target_state = requested.get("state", previous_state)
    if target_state == previous_state and all(
        getattr(current, k) == v for k, v in requested.items()
    ):
        db.commit()
        return current
    if target_state == "withdrawn":
        if period and period.withdrawal_deadline and business_date() > period.withdrawal_deadline:
            raise HTTPException(status_code=409, detail="Ya venció el plazo de retiro")
    elif target_state != previous_state:
        raise HTTPException(
            409,
            "Aquí solo se admite el retiro; el cierre académico se hace desde las calificaciones",
        )
    before = snapshot(current, AUDITED_FIELDS)
    enrollment = update_enrollment(db, enrollment_id, enrollment_data)
    if target_state == "withdrawn":
        enrollment.waitlist_position = None
        db.flush()

    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Inscripción no encontrada"
        )

    record(
        db,
        actor,
        "enrollment.withdrawn" if target_state == "withdrawn" else "enrollment.updated",
        f"enrollment:{enrollment_id}",
        f"{describe(enrollment)}; {changes(before, snapshot(enrollment, AUDITED_FIELDS))}",
    )
    if previous_state == "enrolled" and target_state == "withdrawn":
        promote_waitlist(db, enrollment.section_id, enrollment.period, actor)
    db.commit()
    db.refresh(enrollment)
    return enrollment


def promote_waitlist(db, section_id, period, actor=None):
    section = db.get(Section, section_id)
    waiting = (
        db.query(Enrollment)
        .filter_by(section_id=section_id, period=period, state="waitlisted")
        .order_by(
            Enrollment.waitlist_position, Enrollment.enrollment_date, Enrollment.enrollment_id
        )
        .all()
    )
    for candidate in waiting:
        if occupied_seats(db, section_id, period) >= section.capacity:
            break
        try:
            validate_eligibility(
                db,
                EnrollmentCreate(
                    student_id=candidate.student_id, section_id=section_id, period=period
                ),
                exclude_id=candidate.enrollment_id,
            )
        except HTTPException as exc:
            if exc.status_code not in {404, 409}:
                raise
            # Preserve ineligible candidates and their queue position. They may
            # regain eligibility; do not grant a place or remove them silently.
            continue
        candidate.state = "enrolled"
        candidate.waitlist_position = None
        db.flush()
        record(
            db,
            actor,
            "enrollment.promoted",
            f"enrollment:{candidate.enrollment_id}",
            f"{describe(candidate)}; promovido desde la lista de espera",
        )


def delete_enrollment_service(db: Session, enrollment_id: int, actor=None):
    lock_governance(db)
    current = get_enrollment_by_id(db, enrollment_id)
    if current:
        selection_period(db, current.section_id, current.period)
    if current and (
        current.grades
        or current.attendances
        or db.scalar(
            select(AttendanceChange.enrollment_id).filter_by(enrollment_id=enrollment_id).limit(1)
        )
        is not None
        or db.scalar(
            select(Submission.submission_id)
            .join(Assignment, Assignment.assignment_id == Submission.assignment_id)
            .where(
                Assignment.section_id == current.section_id,
                Submission.student_id == current.student_id,
            )
            .limit(1)
        )
        is not None
    ):
        raise HTTPException(
            status_code=409,
            detail=f"La selección {enrollment_id} tiene historial académico. Usa el retiro para conservar el expediente",
        )
    section_id, period, previous_state = (
        (current.section_id, current.period, current.state) if current else (None, None, None)
    )
    summary = describe(current) if current else ""
    enrollment = delete_enrollment(db, enrollment_id)

    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Inscripción no encontrada"
        )

    record(db, actor, "enrollment.deleted", f"enrollment:{enrollment_id}", summary)
    if previous_state == "enrolled":
        promote_waitlist(db, section_id, period, actor)
    db.commit()
    return {"message": "Inscripción eliminada"}
