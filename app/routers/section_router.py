from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import (
    ACADEMIC_SCOPE,
    ensure_section_access,
    get_current_user,
    has_scope,
    require_permissions,
)
from app.db.Session import get_db
from app.models.user_model import User
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
section_manager = require_permissions("academic.manage", fallback_roles=("admin",))


@router.post("/", response_model=SectionOut, dependencies=[Depends(section_manager)])
def create_section(section_data: SectionCreate, db: Session = Depends(get_db)):
    return create_section_service(db, section_data)


@router.get("/", response_model=list[SectionOut])
def get_sections(
    q: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    sections = get_sections_service(db)
    if not has_scope(user, *ACADEMIC_SCOPE):
        if user.teacher_id is None:
            sections = []
        else:
            sections = [item for item in sections if item.teacher_id == user.teacher_id]
    sections.sort(key=lambda item: item.section_id)
    return paginate_and_filter(
        sections, skip, limit, q, ("code", "description", "subject_code", "subject_name")
    )


@router.get("/{section_id}", response_model=SectionOut)
def get_section_by_id(
    section_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_section_access(db, user, section_id, allow_student=True)
    return get_section_by_id_service(db, section_id)


@router.patch("/{section_id}", response_model=SectionOut)
def update_section(
    section_id: int,
    section_data: SectionUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(section_manager),
):
    return update_section_service(db, section_id, section_data, actor)


@router.delete("/{section_id}", dependencies=[Depends(section_manager)])
def delete_section(section_id: int, db: Session = Depends(get_db)):
    return delete_section_service(db, section_id)
