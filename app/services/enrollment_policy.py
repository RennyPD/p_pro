"""Period invariants shared by service and internal persistence entry points."""

from fastapi import HTTPException

from app.models.configuration_model import AcademicPeriod
from app.models.section_model import Section
from app.services.business_time import business_date


def selection_period(db, section_id: int, name: str, *, registration: bool = False):
    section = db.get(Section, section_id)
    if section is None:
        raise HTTPException(404, "No se encontró la sección")
    period = db.query(AcademicPeriod).filter_by(name=name).first()
    if period is None:
        raise HTTPException(409, "El período académico no existe")
    # Empty period_name is retained for legacy sections. Existing historical
    # records are not renamed or migrated implicitly.
    if section.period_name and section.period_name != name:
        raise HTTPException(409, "El período de la selección no coincide con el de la sección")
    if period.status == "closed":
        raise HTTPException(409, "El período académico está cerrado")
    if registration:
        if period.status not in {"registration", "active"}:
            raise HTTPException(409, "La selección está cerrada para este período")
        today = business_date()
        if period.registration_start and today < period.registration_start:
            raise HTTPException(409, "La selección aún no ha comenzado")
        if period.registration_end and today > period.registration_end:
            raise HTTPException(409, "La selección está cerrada para este período")
    return period
