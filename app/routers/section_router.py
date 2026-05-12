from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.Sesssion import get_db

from app.schemas.section_schema import (
    SectionUpdate,
    SectionCreate,
    SectionOut
)

from app.services.section_service import(
    create_section_service,
    get_sections_service,
    get_section_by_id_service,
    update_section_service,
    delete_section_service
)

router = APIRouter(
    prefix="/sections",
    tags=["sections"]
)

@router.post("/", response_model=SectionOut)
def create_section(
    section_data: SectionCreate,
    db: Session = Depends(get_db)
):
    return create_section_service(db, section_data)

@router.get("/", response_model= list[SectionOut])
def get_sections(
    db: Session = Depends(get_db)
):
    return get_sections_service(db)

@router.get("/{section_id}", response_model=SectionOut)
def get_teacher_by_id(
    section_id: int,
    db: Session = Depends(get_db)
):
    return get_section_by_id_service(db, section_id)

@router.put("/{section_id}", response_model= SectionOut)
def update_section(
    section_id: int,
    section_data: SectionUpdate,
    db: Session = Depends(get_db)
):
    return update_section_service(db, section_id, section_data)

@router.delete("/{section_id}")
def delete_section(
    section_id: int,
    db: Session = Depends(get_db)
):
    return delete_section_service(db, section_id  )