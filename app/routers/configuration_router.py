from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_roles
from app.db.Session import get_db
from app.models.assessment_model import Assessment
from app.models.configuration_model import AcademicPeriod, InstitutionSettings
from app.models.enrollment_model import Enrollment
from app.models.section_model import Section
from app.schemas.configuration_schema import (
    AcademicPeriodCreate,
    AcademicPeriodOut,
    AcademicPeriodUpdate,
    InstitutionSettingsOut,
    InstitutionSettingsUpdate,
)

router = APIRouter(tags=["academic configuration"])


def get_or_create_settings(db: Session) -> InstitutionSettings:
    settings = db.get(InstitutionSettings, 1)
    if settings is None:
        settings = InstitutionSettings(settings_id=1)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def enrollment_number(settings: InstitutionSettings) -> str:
    year = datetime.now(UTC).year
    sequence = str(settings.next_enrollment_number).zfill(settings.enrollment_digits)
    return f"{settings.enrollment_prefix}-{year}-{sequence}"


def settings_out(settings: InstitutionSettings) -> InstitutionSettingsOut:
    return InstitutionSettingsOut(
        settings_id=settings.settings_id,
        institution_name=settings.institution_name,
        enrollment_prefix=settings.enrollment_prefix,
        enrollment_digits=settings.enrollment_digits,
        passing_grade=settings.passing_grade,
        max_credits_per_period=settings.max_credits_per_period,
        next_enrollment_number=settings.next_enrollment_number,
        enrollment_preview=enrollment_number(settings),
    )


@router.get("/configuration/institution", response_model=InstitutionSettingsOut)
def get_institution_settings(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return settings_out(get_or_create_settings(db))


@router.put(
    "/configuration/institution",
    response_model=InstitutionSettingsOut,
    dependencies=[Depends(require_roles("admin"))],
)
def update_institution_settings(data: InstitutionSettingsUpdate, db: Session = Depends(get_db)):
    settings = get_or_create_settings(db)
    for key, value in data.model_dump().items():
        setattr(settings, key, value)
    db.commit()
    db.refresh(settings)
    return settings_out(settings)


@router.post(
    "/periods/",
    response_model=AcademicPeriodOut,
    dependencies=[Depends(require_roles("admin"))],
)
def create_period(data: AcademicPeriodCreate, db: Session = Depends(get_db)):
    if data.active:
        db.query(AcademicPeriod).update({AcademicPeriod.active: False})
    period = AcademicPeriod(**data.model_dump())
    db.add(period)
    db.commit()
    db.refresh(period)
    return period


@router.get("/periods/", response_model=list[AcademicPeriodOut])
def list_periods(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return db.query(AcademicPeriod).order_by(AcademicPeriod.start_date.desc()).all()


@router.patch(
    "/periods/{period_id}",
    response_model=AcademicPeriodOut,
    dependencies=[Depends(require_roles("admin"))],
)
def update_period(period_id: int, data: AcademicPeriodUpdate, db: Session = Depends(get_db)):
    period = db.get(AcademicPeriod, period_id)
    if period is None:
        raise HTTPException(status_code=404, detail="Academic period not found")
    values = data.model_dump(exclude_unset=True)
    if values.get("status") == "closed" and period.status != "closed":
        raise HTTPException(status_code=409, detail="Use the controlled period closing process")
    if values.get("active"):
        db.query(AcademicPeriod).update({AcademicPeriod.active: False})
    for key, value in values.items():
        setattr(period, key, value)
    if period.start_date >= period.end_date:
        raise HTTPException(status_code=422, detail="End date must be later than start date")
    db.commit()
    db.refresh(period)
    return period


@router.post("/periods/{period_id}/close", dependencies=[Depends(require_roles("admin"))])
def close_period(period_id: int, db: Session = Depends(get_db)):
    period = db.get(AcademicPeriod, period_id)
    if period is None:
        raise HTTPException(status_code=404, detail="Academic period not found")
    if period.status == "closed":
        return {"period_id": period_id, "status": "closed", "sections_closed": 0}
    sections = db.query(Section).filter(Section.period_name == period.name).all()
    incomplete = []
    for section in sections:
        assessments = db.query(Assessment).filter_by(section_id=section.section_id).all()
        total_weight = sum(item.weight for item in assessments)
        if (
            not assessments
            or abs(total_weight - 100) > 0.001
            or not all(item.closed for item in assessments)
        ):
            incomplete.append(section.code)
    if incomplete:
        raise HTTPException(
            status_code=409,
            detail=f"Sections with incomplete assessments: {', '.join(incomplete)}",
        )
    for section in sections:
        section.status = "closed"
        db.query(Enrollment).filter(
            Enrollment.section_id == section.section_id,
            Enrollment.period == period.name,
            Enrollment.state == "enrolled",
        ).update({Enrollment.state: "completed"}, synchronize_session=False)
    period.status = "closed"
    period.active = False
    db.commit()
    return {"period_id": period_id, "status": "closed", "sections_closed": len(sections)}


@router.post("/periods/{period_id}/reopen", response_model=AcademicPeriodOut)
def reopen_period(
    period_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_roles("admin")),
):
    period = db.get(AcademicPeriod, period_id)
    if period is None:
        raise HTTPException(status_code=404, detail="Academic period not found")
    period.status = "active"
    db.query(AcademicPeriod).update({AcademicPeriod.active: False})
    period.active = True
    db.commit()
    db.refresh(period)
    return period


@router.delete("/periods/{period_id}", dependencies=[Depends(require_roles("admin"))])
def delete_period(period_id: int, db: Session = Depends(get_db)):
    period = db.get(AcademicPeriod, period_id)
    if period is None:
        raise HTTPException(status_code=404, detail="Academic period not found")
    db.delete(period)
    db.commit()
    return {"message": "Academic period deleted successfully"}
