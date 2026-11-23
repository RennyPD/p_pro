"""School years and the generation of their periods (Fase 3, block B)."""

from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.configuration_model import AcademicPeriod, SchoolYear
from app.schemas.configuration_schema import SCHEME_PERIODS
from app.services.institution_profile import institution_type

PERIOD_LABELS = {
    "bimester": "Bimestre",
    "trimester": "Trimestre",
    "quarter": "Período",
    "quadrimester": "Cuatrimestre",
    "semester": "Semestre",
    "annual": "Anual",
}


def default_scheme(db: Session) -> str:
    """Four MINERD periods in schools (decision 3), two semesters elsewhere."""
    return "quarters" if institution_type(db) == "school" else "semesters"


def split_dates(start: date, end: date, parts: int) -> list[tuple[date, date]]:
    """Consecutive ranges covering start..end (inclusive) as evenly as possible."""
    total = (end - start).days + 1
    if total < parts * 2:
        raise HTTPException(409, "El año lectivo es demasiado corto para ese esquema de períodos")
    bounds = [start + timedelta(days=total * index // parts) for index in range(parts + 1)]
    return [(bounds[i], bounds[i + 1] - timedelta(days=1)) for i in range(parts)]


def period_name(year: SchoolYear, period_type: str, sequence: int, parts: int) -> str:
    label = PERIOD_LABELS[period_type]
    return f"{label} · {year.name}" if parts == 1 else f"{label} {sequence} · {year.name}"


def generate_periods(db: Session, year: SchoolYear) -> list[AcademicPeriod]:
    if year.period_count:
        raise HTTPException(409, "Este año lectivo ya tiene períodos; edítalos desde la lista")
    period_type, parts = SCHEME_PERIODS[year.period_scheme]
    created = []
    for sequence, (start, end) in enumerate(
        split_dates(year.start_date, year.end_date, parts), start=1
    ):
        name = period_name(year, period_type, sequence, parts)
        if db.query(AcademicPeriod.period_id).filter_by(name=name).first():
            raise HTTPException(409, f"Ya existe el período {name}. Renómbralo antes de generar")
        period = AcademicPeriod(
            name=name,
            start_date=start,
            end_date=end,
            active=False,
            status="planning",
            period_type=period_type,
            sequence=sequence,
            school_year=year,
        )
        db.add(period)
        created.append(period)
    db.flush()
    return created


def ensure_periods_fit(year: SchoolYear, start: date, end: date) -> None:
    for period in year.periods:
        if period.start_date < start or period.end_date > end:
            raise HTTPException(
                409, f"El período {period.name} quedaría fuera de las fechas del año lectivo"
            )
