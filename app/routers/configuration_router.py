import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_permissions
from app.db.Session import get_db
from app.models.assessment_model import Assessment
from app.models.configuration_model import AcademicPeriod, InstitutionSettings
from app.models.enrollment_model import CourseSelectionCart, Enrollment
from app.models.section_model import Section
from app.schemas.configuration_schema import (
    AcademicPeriodBase,
    AcademicPeriodCreate,
    AcademicPeriodOut,
    AcademicPeriodUpdate,
    InstitutionSettingsBase,
    InstitutionSettingsOut,
    InstitutionSettingsUpdate,
    OperationReason,
)
from app.services.academic_grading import academic_result
from app.services.governance_workflow import history, lock_governance, record

router = APIRouter(tags=["academic configuration"])
academic_manager = require_permissions("academic.manage", fallback_roles=("admin",))


def get_or_create_settings(db, write=False):
    item = db.get(InstitutionSettings, 1)
    if item is None:
        item = InstitutionSettings(
            settings_id=1,
            institution_name="Nexo Académico",
            enrollment_prefix="EST",
            enrollment_digits=4,
            next_enrollment_number=1,
            passing_grade=70,
            max_credits_per_period=24,
            revision=0,
        )
        if write:
            db.add(item)
            db.flush()
    return item


def enrollment_number(settings):
    return f"{settings.enrollment_prefix}-{datetime.now(UTC).year}-{str(settings.next_enrollment_number).zfill(settings.enrollment_digits)}"


def settings_out(settings):
    return InstitutionSettingsOut(
        **{k: getattr(settings, k) for k in InstitutionSettingsBase.model_fields},
        settings_id=settings.settings_id,
        next_enrollment_number=settings.next_enrollment_number,
        enrollment_preview=enrollment_number(settings),
        revision=settings.revision,
    )


@router.get("/configuration/institution", response_model=InstitutionSettingsOut)
def get_institution_settings(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return settings_out(get_or_create_settings(db))


@router.post("/configuration/institution/preview", dependencies=[Depends(academic_manager)])
def settings_preview(data: InstitutionSettingsUpdate, db: Session = Depends(get_db)):
    current = get_or_create_settings(db)
    return {
        "revision": current.revision,
        "changes": [
            {"field": k, "before": getattr(current, k), "after": getattr(data, k)}
            for k in InstitutionSettingsBase.model_fields
            if getattr(current, k) != getattr(data, k)
        ],
        "existing_selections_preserved": db.query(Enrollment).count(),
        "policy": "La nota aprobatoria se conserva por selección existente. La nueva nota y el límite de créditos se aplican a nuevas selecciones; no se retiran materias existentes.",
    }


@router.put("/configuration/institution", response_model=InstitutionSettingsOut)
def update_institution_settings(
    data: InstitutionSettingsUpdate, db: Session = Depends(get_db), user=Depends(academic_manager)
):
    lock_governance(db)
    settings = get_or_create_settings(db, True)
    if data.expected_revision is not None and data.expected_revision != settings.revision:
        raise HTTPException(409, "La configuración cambió; recarga y revisa el impacto nuevamente")
    if not data.institution_name.strip() or len(data.reason.strip()) < 3:
        raise HTTPException(422, "Nombre y motivo son obligatorios")
    db.query(Enrollment).filter(Enrollment.passing_grade.is_(None)).update(
        {Enrollment.passing_grade: settings.passing_grade}, synchronize_session=False
    )
    for key in InstitutionSettingsBase.model_fields:
        before, after = getattr(settings, key), getattr(data, key)
        if before != after:
            record(
                db,
                user,
                "configuration.updated",
                "institution-settings",
                f"{data.reason[:250]}; {key}: {before} → {after}",
            )
        setattr(settings, key, after)
    settings.revision += 1
    db.commit()
    return settings_out(settings)


@router.get("/configuration/institution/history", dependencies=[Depends(academic_manager)])
def institution_history(db: Session = Depends(get_db)):
    return history(db, "institution-settings")


def used_period(db, period):
    return bool(
        db.query(Section).filter_by(period_name=period.name).first()
        or db.query(Enrollment).filter_by(period=period.name).first()
        or db.query(CourseSelectionCart).filter_by(period=period.name).first()
    )


def validated(values):
    try:
        return AcademicPeriodBase(**values)
    except ValidationError as exc:
        raise HTTPException(422, str(exc))


@router.post("/periods/", response_model=AcademicPeriodOut)
def create_period(
    data: AcademicPeriodCreate, db: Session = Depends(get_db), user=Depends(academic_manager)
):
    lock_governance(db)
    if data.status == "closed":
        raise HTTPException(409, "Crea el período abierto y usa su cierre controlado")
    if data.active:
        db.query(AcademicPeriod).update({AcademicPeriod.active: False})
    period = AcademicPeriod(**data.model_dump())
    db.add(period)
    db.flush()
    record(
        db,
        user,
        "period.created",
        f"period:{period.period_id}",
        f"Creación: {period.name}; {period.start_date} → {period.end_date}",
    )
    db.commit()
    return period


@router.get("/periods/", response_model=list[AcademicPeriodOut])
def list_periods(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return db.query(AcademicPeriod).order_by(AcademicPeriod.start_date.desc()).all()


@router.patch("/periods/{period_id}", response_model=AcademicPeriodOut)
def update_period(
    period_id: int,
    data: AcademicPeriodUpdate,
    db: Session = Depends(get_db),
    user=Depends(academic_manager),
):
    lock_governance(db)
    period = db.get(AcademicPeriod, period_id)
    if period is None:
        raise HTTPException(404, "Período no encontrado")
    values = data.model_dump(exclude_unset=True)
    if period.status == "closed" and values:
        raise HTTPException(409, "Reabre el período antes de editarlo")
    if values.get("status") == "closed":
        raise HTTPException(409, "Usa el cierre controlado del período")
    if "name" in values and values["name"] != period.name and used_period(db, period):
        raise HTTPException(
            409, "No se renombra un período con secciones, selecciones o carritos vinculados"
        )
    combined = {k: getattr(period, k) for k in AcademicPeriodBase.model_fields} | values
    validated(combined)
    if values.get("active"):
        db.query(AcademicPeriod).update({AcademicPeriod.active: False})
    for key, value in values.items():
        record(
            db,
            user,
            "period.updated",
            f"period:{period_id}",
            f"{key}: {getattr(period, key)} → {value}",
        )
        setattr(period, key, value)
    db.commit()
    return period


@router.get("/periods/{period_id}/closing-preview", dependencies=[Depends(academic_manager)])
def closing_preview(period_id: int, db: Session = Depends(get_db)):
    period = db.get(AcademicPeriod, period_id)
    if period is None:
        raise HTTPException(404, "Período no encontrado")
    sections = db.query(Section).filter_by(period_name=period.name).order_by(Section.code).all()
    blockers = []
    # Orphaned/mismatched sections would otherwise escape the closure check.
    for enrollment in db.query(Enrollment).filter_by(period=period.name):
        if enrollment.section.period_name != period.name and enrollment.state in {
            "enrolled",
            "completed",
            "failed",
        }:
            blockers.append(f"{enrollment.section.code}: asignación de período inconsistente")
    for section in sections:
        roster = (
            db.query(Enrollment)
            .filter(
                Enrollment.section_id == section.section_id,
                Enrollment.period == period.name,
                Enrollment.state.in_(("enrolled", "completed", "failed")),
            )
            .all()
        )
        if not roster:
            continue
        assessments = db.query(Assessment).filter_by(section_id=section.section_id).all()
        if (
            section.status == "cancelled"
            or not assessments
            or abs(sum(a.weight for a in assessments) - 100) > 0.001
            or not all(a.closed for a in assessments)
        ):
            blockers.append(
                f"{section.code}: evaluaciones incompletas, ponderación inválida o sección cancelada con estudiantes"
            )
        missing = [e.student.enrollment_number for e in roster if not academic_result(db, e).final]
        if missing:
            blockers.append(
                f"{section.code}: notas publicadas faltantes ({', '.join(missing[:10])})"
            )
    return {
        "period_id": period_id,
        "sections": len(sections),
        "can_close": not blockers,
        "blockers": blockers,
        "restorable": bool(period.closure_snapshot),
    }


@router.post("/periods/{period_id}/close")
def close_period(
    period_id: int,
    db: Session = Depends(get_db),
    user=Depends(academic_manager),
    data: OperationReason | None = None,
):
    lock_governance(db)
    preview = closing_preview(period_id, db)
    period = db.get(AcademicPeriod, period_id)
    if period.status == "closed":
        return {"period_id": period_id, "status": "closed", "sections_closed": 0}
    if not preview["can_close"]:
        raise HTTPException(409, "; ".join(preview["blockers"]))
    sections = db.query(Section).filter_by(period_name=period.name).all()
    snapshot = {"sections": {}, "enrollments": {}, "period_status": period.status}
    for section in sections:
        if section.status not in {"cancelled", "closed"}:
            snapshot["sections"][str(section.section_id)] = section.status
            section.status = "closed"
        for enrollment in section.enrollments:
            if enrollment.period == period.name and enrollment.state == "enrolled":
                snapshot["enrollments"][str(enrollment.enrollment_id)] = enrollment.state
                enrollment.state = (
                    "completed" if academic_result(db, enrollment).status == "passed" else "failed"
                )
    period.closure_snapshot = json.dumps(snapshot)
    period.status, period.active = "closed", False
    record(
        db,
        user,
        "period.closed",
        f"period:{period_id}",
        f"{data.reason if data else 'Cierre académico controlado'}; cierre verificado: {len(snapshot['sections'])} secciones; {len(snapshot['enrollments'])} selecciones",
    )
    db.commit()
    return {
        "period_id": period_id,
        "status": "closed",
        "sections_closed": len(snapshot["sections"]),
    }


@router.post("/periods/{period_id}/reopen", response_model=AcademicPeriodOut)
def reopen_period(
    period_id: int,
    db: Session = Depends(get_db),
    user=Depends(academic_manager),
    data: OperationReason | None = None,
):
    lock_governance(db)
    period = db.get(AcademicPeriod, period_id)
    if period is None:
        raise HTTPException(404, "Período no encontrado")
    if period.status != "closed":
        raise HTTPException(409, "El período no está cerrado")
    if period.closure_snapshot:
        snapshot = json.loads(period.closure_snapshot)
        for identifier, state in snapshot["sections"].items():
            section = db.get(Section, int(identifier))
            if section and section.period_name == period.name and section.status == "closed":
                section.status = state
        for identifier, state in snapshot["enrollments"].items():
            enrollment = db.get(Enrollment, int(identifier))
            if (
                enrollment
                and enrollment.period == period.name
                and enrollment.state in {"completed", "failed"}
            ):
                enrollment.state = state
    db.query(AcademicPeriod).update({AcademicPeriod.active: False})
    period.status, period.active = "active", True
    record(
        db,
        user,
        "period.reopened",
        f"period:{period_id}",
        (data.reason + "; " if data else "")
        + (
            "Reapertura con restauración de estados"
            if period.closure_snapshot
            else "Reapertura histórica sin estados previos: secciones conservadas, requieren revisión manual"
        ),
    )
    db.commit()
    return period


@router.get("/periods/{period_id}/history", dependencies=[Depends(academic_manager)])
def period_history(period_id: int, db: Session = Depends(get_db)):
    return history(db, f"period:{period_id}")


@router.delete("/periods/{period_id}")
def delete_period(period_id: int, db: Session = Depends(get_db), user=Depends(academic_manager)):
    lock_governance(db)
    period = db.get(AcademicPeriod, period_id)
    if period is None:
        raise HTTPException(404, "Período no encontrado")
    if used_period(db, period) or period.status != "planning" or period.active:
        raise HTTPException(
            409, "Solo se elimina un período de planificación, sin uso y no vigente"
        )
    record(
        db,
        user,
        "period.deleted",
        f"period:{period_id}",
        f"Eliminación de planificación sin uso: {period.name}",
    )
    db.delete(period)
    db.commit()
    return {"message": "Período sin uso eliminado"}
