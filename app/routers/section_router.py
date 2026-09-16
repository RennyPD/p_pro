from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_roles
from app.db.Session import get_db
from app.pagination import paginate_and_filter
from app.schemas.section_schema import SectionCreate, SectionOut, SectionUpdate
from app.services.section_service import (
    create_section_service,
    delete_section_service,
    get_section_by_id_service,
    get_sections_service,
    update_section_service,
)

router = APIRouter(prefix="/sections", tags=["sections"])


@router.post("/", response_model=SectionOut, dependencies=[Depends(require_roles("admin"))])
def create_section(section_data: SectionCreate, db: Session = Depends(get_db)):
    return create_section_service(db, section_data)


@router.get("/", response_model=list[SectionOut], dependencies=[Depends(get_current_user)])
def get_sections(
    q: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return paginate_and_filter(get_sections_service(db), skip, limit, q, ("code", "description"))


@router.get("/{section_id}", response_model=SectionOut, dependencies=[Depends(get_current_user)])
def get_teacher_by_id(section_id: int, db: Session = Depends(get_db)):
    return get_section_by_id_service(db, section_id)


@router.patch(
    "/{section_id}", response_model=SectionOut, dependencies=[Depends(require_roles("admin"))]
)
def update_section(section_id: int, section_data: SectionUpdate, db: Session = Depends(get_db)):
    return update_section_service(db, section_id, section_data)


@router.delete("/{section_id}", dependencies=[Depends(require_roles("admin"))])
def delete_section(section_id: int, db: Session = Depends(get_db)):
    return delete_section_service(db, section_id)
