from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.configuration_model import AcademicPeriod
from app.repositories.section_repository import (
    create_section,
    delete_section,
    get_section_by_id,
    get_sections,
    update_section,
)
from app.schemas.section_schema import SectionCreate, SectionUpdate
from app.services.governance_workflow import lock_governance


def create_section_service(db: Session, section_data: SectionCreate):
    lock_governance(db)
    validate_period(db, section_data.period_name)
    sections = get_sections(db)

    for section in sections:
        if section.code == section_data.code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Code already exist"
            )

    return create_section(db, section_data)


def get_sections_service(db: Session):
    return get_sections(db)


def get_section_by_id_service(db, section_id):

    section = get_section_by_id(db, section_id)
    if not section:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")

    return section


def update_section_service(db: Session, section_id: int, section_data: SectionUpdate):
    lock_governance(db)
    current = get_section_by_id(db, section_id)
    if current is None:
        raise HTTPException(404, "Section not found")
    changes = section_data.model_dump(exclude_unset=True)
    if any(value is None for value in changes.values()):
        raise HTTPException(422, "Section fields cannot be null")
    target_period = changes.get("period_name", current.period_name)
    validate_period(db, target_period)
    if target_period != current.period_name and current.enrollments:
        raise HTTPException(409, "A section with academic history cannot change period")
    capacity = changes.get("capacity", current.capacity)
    counts = {}
    for item in current.enrollments:
        if item.state == "enrolled":
            counts[item.period] = counts.get(item.period, 0) + 1
    if any(count > capacity for count in counts.values()):
        raise HTTPException(409, "Capacity cannot be lower than confirmed selections")
    section = update_section(db, section_id, section_data)

    if not section:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")

    return section


def validate_period(db, name):
    if name and db.query(AcademicPeriod).filter_by(name=name).first() is None:
        raise HTTPException(409, "The academic period does not exist")


def delete_section_service(db: Session, section_id: int):

    section = delete_section(db, section_id)

    if not section:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")

    return {"Message": "Section removed"}
