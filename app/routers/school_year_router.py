"""School years: create, edit, delete and generate their periods (Fase 3, block B)."""

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_permissions
from app.db.Session import get_db
from app.models.configuration_model import SchoolYear
from app.pagination import page_query, search
from app.schemas.configuration_schema import (
    AcademicPeriodOut,
    SchoolYearBase,
    SchoolYearCreate,
    SchoolYearOut,
    SchoolYearUpdate,
)
from app.services.governance_workflow import lock_governance, record
from app.services.school_years import default_scheme, ensure_periods_fit, generate_periods

router = APIRouter(tags=["academic configuration"])
academic_manager = require_permissions("settings.manage")


def year_or_404(db: Session, school_year_id: int) -> SchoolYear:
    year = db.get(SchoolYear, school_year_id)
    if year is None:
        raise HTTPException(404, "Año lectivo no encontrado")
    return year


def ensure_unique_name(db: Session, name: str, current: SchoolYear | None = None) -> None:
    other = db.query(SchoolYear).filter_by(name=name).first()
    if other is not None and other is not current:
        raise HTTPException(409, f"Ya existe el año lectivo {name}")


@router.get("/school-years/", response_model=list[SchoolYearOut])
def list_school_years(
    response: Response,
    q: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int | None = Query(None, ge=1, le=100),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    query = search(db.query(SchoolYear), q, SchoolYear.name)
    return page_query(
        query.order_by(SchoolYear.start_date.desc(), SchoolYear.school_year_id.desc()),
        response,
        skip,
        limit,
    )


@router.post("/school-years/", response_model=SchoolYearOut)
def create_school_year(
    data: SchoolYearCreate, db: Session = Depends(get_db), user=Depends(academic_manager)
):
    lock_governance(db)
    ensure_unique_name(db, data.name)
    year = SchoolYear(**data.model_dump(exclude={"period_scheme"}))
    year.period_scheme = data.period_scheme or default_scheme(db)
    db.add(year)
    db.flush()
    record(
        db,
        user,
        "school_year.created",
        f"school-year:{year.school_year_id}",
        f"Creación: {year.name}; {year.start_date} → {year.end_date}; {year.period_scheme}",
    )
    db.commit()
    db.refresh(year)
    return year


@router.patch("/school-years/{school_year_id}", response_model=SchoolYearOut)
def update_school_year(
    school_year_id: int,
    data: SchoolYearUpdate,
    db: Session = Depends(get_db),
    user=Depends(academic_manager),
):
    lock_governance(db)
    year = year_or_404(db, school_year_id)
    values = data.model_dump(exclude_unset=True, exclude_none=True)
    combined = {key: getattr(year, key) for key in SchoolYearBase.model_fields} | values
    try:
        checked = SchoolYearBase(**combined)
    except ValidationError as exc:
        raise HTTPException(422, str(exc))
    ensure_unique_name(db, checked.name, year)
    ensure_periods_fit(year, checked.start_date, checked.end_date)
    if "period_scheme" in values and values["period_scheme"] != year.period_scheme:
        if year.period_count:
            raise HTTPException(409, "El esquema solo cambia mientras el año no tiene períodos")
    for key in values:
        new = getattr(checked, key)
        if new != getattr(year, key):
            record(
                db,
                user,
                "school_year.updated",
                f"school-year:{school_year_id}",
                f"{key}: {getattr(year, key)} → {new}",
            )
            setattr(year, key, new)
    db.commit()
    db.refresh(year)
    return year


@router.delete("/school-years/{school_year_id}")
def delete_school_year(
    school_year_id: int, db: Session = Depends(get_db), user=Depends(academic_manager)
):
    lock_governance(db)
    year = year_or_404(db, school_year_id)
    if year.period_count:
        raise HTTPException(409, "Solo se elimina un año lectivo sin períodos")
    record(
        db,
        user,
        "school_year.deleted",
        f"school-year:{school_year_id}",
        f"Eliminación: {year.name}",
    )
    db.delete(year)
    db.commit()
    return {"message": "Año lectivo eliminado"}


@router.post(
    "/school-years/{school_year_id}/generate-periods", response_model=list[AcademicPeriodOut]
)
def generate_school_year_periods(
    school_year_id: int, db: Session = Depends(get_db), user=Depends(academic_manager)
):
    lock_governance(db)
    year = year_or_404(db, school_year_id)
    periods = generate_periods(db, year)
    record(
        db,
        user,
        "school_year.periods_generated",
        f"school-year:{school_year_id}",
        f"{len(periods)} períodos: " + ", ".join(period.name for period in periods),
    )
    db.commit()
    return periods
