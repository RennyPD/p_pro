from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.auth import (
    ACADEMIC_SCOPE,
    ensure_section_access,
    get_current_user,
    has_scope,
    require_permissions,
)
from app.db.Session import get_db
from app.models.section_model import Section
from app.models.subject_model import Subject
from app.models.user_model import User
from app.pagination import page_query, search
from app.schemas.section_schema import SectionCreate, SectionOut, SectionUpdate
from app.services.governance_workflow import lock_governance
from app.services.section_service import (
    create_section_service,
    delete_section_service,
    get_section_by_id_service,
    update_section_service,
)

router = APIRouter(prefix="/sections", tags=["sections"])
section_manager = require_permissions("sections.manage")


@router.post("/", response_model=SectionOut)
def create_section(
    section_data: SectionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(section_manager),
):
    return create_section_service(db, section_data, user)


@router.get("/", response_model=list[SectionOut])
def get_sections(
    response: Response,
    q: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Section)
    if not has_scope(user, *ACADEMIC_SCOPE):
        if user.teacher_id is None:
            return []
        query = query.filter(Section.teacher_id == user.teacher_id)
    if q and q.strip():
        query = search(
            query.outerjoin(Section.subject),
            q,
            Section.code,
            Section.description,
            Subject.code,
            Subject.description,
        )
    return page_query(query.order_by(Section.section_id), response, skip, limit)


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


@router.delete("/{section_id}")
def delete_section(
    section_id: int, db: Session = Depends(get_db), user: User = Depends(section_manager)
):
    lock_governance(db)
    return delete_section_service(db, section_id, user)
