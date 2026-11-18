from types import SimpleNamespace

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.assessment_model import Assessment
from app.models.configuration_model import AcademicPeriod
from app.models.operations_model import Assignment, LessonPlan
from app.models.subject_model import Subject
from app.models.teacher_model import Teacher
from app.repositories.section_repository import (
    create_section,
    delete_section,
    get_section_by_id,
    get_sections,
    update_section,
)
from app.schemas.section_schema import SectionCreate, SectionUpdate
from app.services.effective_schedule import effective_blocks, legacy_blocks, validate_schedule
from app.services.governance_workflow import lock_governance, record


def create_section_service(db: Session, section_data: SectionCreate):
    lock_governance(db)
    validate_period(db, section_data.period_name)
    validate_people(db, section_data.subject_id, section_data.teacher_id)
    sections = get_sections(db)

    for section in sections:
        if section.code == section_data.code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe un registro con ese código",
            )

    return create_section(db, section_data)


def get_sections_service(db: Session):
    return get_sections(db)


def get_section_by_id_service(db, section_id):

    section = get_section_by_id(db, section_id)
    if not section:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No se encontró la sección"
        )

    return section


def update_section_service(db: Session, section_id: int, section_data: SectionUpdate, actor=None):
    lock_governance(db)
    current = get_section_by_id(db, section_id)
    if current is None:
        raise HTTPException(404, "No se encontró la sección")
    changes = section_data.model_dump(exclude_unset=True)
    if any(value is None for value in changes.values()):
        raise HTTPException(422, "Los campos de la sección no pueden quedar vacíos")
    if changes.get("subject_id", current.subject_id) != current.subject_id and (
        current.enrollments
        or any(
            db.query(model).filter_by(section_id=section_id).first() is not None
            for model in (Assessment, Assignment, LessonPlan)
        )
    ):
        raise HTTPException(
            409,
            f"La sección {current.code} ya tiene historial. Crea otra sección para la nueva asignatura",
        )
    target_period = changes.get("period_name", current.period_name)
    validate_period(db, target_period)
    if target_period != current.period_name and current.enrollments:
        raise HTTPException(409, "Una sección con historial académico no puede cambiar de período")
    capacity = changes.get("capacity", current.capacity)
    if changes.get("minimum_capacity", current.minimum_capacity) > capacity:
        raise HTTPException(422, "El cupo mínimo no puede superar la capacidad de la sección")
    if changes.get("start_time", current.start_time) >= changes.get("end_time", current.end_time):
        raise HTTPException(422, "La hora final debe ser posterior a la hora de inicio")
    validate_people(
        db,
        changes.get("subject_id", current.subject_id),
        changes.get("teacher_id", current.teacher_id),
    )
    schedule_fields = {
        "status",
        "teacher_id",
        "days_of_week",
        "start_time",
        "end_time",
        "period_name",
        "room",
        "modality",
        "capacity",
    }
    schedule_changed = any(
        value != getattr(current, key)
        for key, value in changes.items()
        if key in schedule_fields and key != "days_of_week"
    ) or (
        "days_of_week" in changes
        and [day.value for day in changes["days_of_week"]] != current.days_of_week.split(", ")
    )
    publishing = current.status == "draft" and changes.get("status") in {"published", "active"}
    if publishing and not target_period:
        raise HTTPException(422, "Selecciona un período académico antes de publicar")
    if schedule_changed:
        validate_section_schedule(db, current, changes, capacity)
    counts = {}
    for item in current.enrollments:
        if item.state == "enrolled":
            counts[item.period] = counts.get(item.period, 0) + 1
    if any(count > capacity for count in counts.values()):
        raise HTTPException(409, "El cupo no puede ser menor que las selecciones confirmadas")
    if actor is not None and schedule_changed:
        record(
            db,
            actor,
            "section.published" if publishing else "section.schedule.updated",
            f"section:{section_id}",
            "Cambios de oferta: " + ", ".join(sorted(changes.keys() & schedule_fields)),
        )
    section = update_section(db, section_id, section_data)

    if not section:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No se encontró la sección"
        )

    return section


def validate_people(db, subject_id, teacher_id):
    if db.get(Subject, subject_id) is None:
        raise HTTPException(422, "Selecciona una asignatura existente para la sección")
    if db.get(Teacher, teacher_id) is None:
        raise HTTPException(422, "Selecciona un docente existente para la sección")


def validate_section_schedule(db, current, changes, capacity):
    proposed = SimpleNamespace(
        **{
            field: changes.get(field, getattr(current, field))
            for field in (
                "section_id",
                "code",
                "teacher_id",
                "status",
                "period_name",
                "start_time",
                "end_time",
                "days_of_week",
                "room",
                "modality",
                "enrollments",
            )
        }
    )
    if proposed.status not in {"published", "active"}:
        return
    period = db.query(AcademicPeriod).filter_by(name=proposed.period_name).first()
    if period and period.status == "closed":
        raise HTTPException(409, "El período está cerrado. Reabre el período antes de publicar")
    if isinstance(proposed.days_of_week, list):
        proposed.days_of_week = ", ".join(day.value for day in proposed.days_of_week)
    if current.meetings:
        for meeting in current.meetings:
            if meeting.classroom and (
                not meeting.classroom.active or meeting.classroom.capacity < capacity
            ):
                raise HTTPException(
                    409, f"El aula {meeting.classroom.name} debe estar activa y cubrir el cupo"
                )
        blocks = [
            block if block.classroom_id else block.model_copy(update={"room": proposed.room})
            for block in effective_blocks(current)
        ]
    else:
        blocks = legacy_blocks(proposed)
    if not blocks:
        raise HTTPException(422, "Programa al menos un bloque válido antes de publicar la sección")
    validate_schedule(db, proposed, blocks)


def validate_period(db, name):
    if name and db.query(AcademicPeriod).filter_by(name=name).first() is None:
        raise HTTPException(409, "El período académico no existe")


def delete_section_service(db: Session, section_id: int):

    section = delete_section(db, section_id)

    if not section:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No se encontró la sección"
        )

    return {"Message": "Section removed"}
