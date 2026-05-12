from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.repositories.section_repository import (
    create_section,
    get_sections,
    get_section_by_id,
    update_section,
    delete_section
)

from app.schemas.section_schema import (
    SectionCreate,
    SectionUpdate
)

def create_section_service(db: Session, section_data: SectionCreate):

    sections = get_sections(db)

    for section in sections:
        if section.email == section_data.code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Code already exist"
            )

    return create_section(db, section_data)

def get_sections_service(db:Session):
    return get_sections(db)

def get_section_by_id_service(db, section_id):

    section = get_section_by_id(db, section_id)
    if not section:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Section not found"
        )
    
    return section

def update_section_service(db: Session, section_id: int, section_data: SectionUpdate):

    section = update_section(db, section_id, section_data)

    if not section:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Section not found"
        )

    return section
 
def delete_section_service(db: Session, section_id: int):

    section = delete_section(db, section_id)

    if not section:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Section not found"
        )
    
    return {
        "Message": "Section removed"
    }
    