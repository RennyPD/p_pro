from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.career_model import Career
from app.models.grading_scale_model import GradingScale
from app.repositories.career_repository import (
    create_career,
    delete_career,
    get_career_by_id,
    get_careers,
    update_career,
)
from app.schemas.career_schema import CareerCreate, CareerUpdate
from app.services.audit_log import changes, record, snapshot
from app.services.governance_workflow import lock_governance
from app.services.institution_profile import allowed_levels, institution_type


def ensure_level_fits(db: Session, level: str | None) -> None:
    if level is None:
        return
    kind = institution_type(db)
    if level not in allowed_levels(kind):
        message = (
            "Este nivel es escolar; la institución está configurada como universidad"
            if kind == "university"
            else "Este nivel es universitario; la institución está configurada como escuela"
        )
        raise HTTPException(422, message)


def ensure_scale_exists(db: Session, scale_id: int | None) -> None:
    if scale_id is not None and db.get(GradingScale, scale_id) is None:
        raise HTTPException(422, "La escala de calificación no existe")


def create_career_service(db: Session, data: CareerCreate, actor):
    ensure_level_fits(db, data.academic_level)
    ensure_scale_exists(db, data.grading_scale_id)
    if not data.code:
        highest_id = db.query(func.max(Career.career_id)).scalar() or 0
        data = data.model_copy(update={"code": f"CAR-{highest_id + 1:03d}"})
    career = create_career(db, data)
    record(
        db, actor, "career.created", f"career:{career.career_id}", f"{career.code} {career.name}"
    )
    db.commit()
    db.refresh(career)
    return career


def get_careers_service(db: Session):
    return get_careers(db)


def get_career_service(db: Session, career_id: int):
    career = get_career_by_id(db, career_id)
    if career is None:
        raise HTTPException(status_code=404, detail="Carrera no encontrada")
    return career


def update_career_service(db: Session, career_id: int, data: CareerUpdate, actor):
    lock_governance(db)
    ensure_level_fits(db, data.academic_level)
    ensure_scale_exists(db, data.grading_scale_id)
    fields = sorted(data.model_fields_set)
    before = snapshot(get_career_service(db, career_id), fields)
    career = update_career(db, career_id, data)
    if career is None:
        raise HTTPException(status_code=404, detail="Carrera no encontrada")
    record(
        db,
        actor,
        "career.updated",
        f"career:{career_id}",
        changes(before, snapshot(career, fields)),
    )
    db.commit()
    db.refresh(career)
    return career


def delete_career_service(db: Session, career_id: int, actor):
    career = get_career_service(db, career_id)
    summary = f"{career.code} {career.name}"
    delete_career(db, career_id)
    record(db, actor, "career.deleted", f"career:{career_id}", summary)
    db.commit()
    return {"message": "Carrera eliminada"}
