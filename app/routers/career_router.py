from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_permissions
from app.db.Session import get_db
from app.pagination import paginate_and_filter
from app.schemas.career_schema import CareerCreate, CareerOut, CareerUpdate
from app.services.career_service import (
    create_career_service,
    delete_career_service,
    get_career_service,
    get_careers_service,
    update_career_service,
)

router = APIRouter(prefix="/careers", tags=["careers"])
career_manager = require_permissions("academic.manage", fallback_roles=("admin",))


@router.post("/", response_model=CareerOut, dependencies=[Depends(career_manager)])
def create_career(data: CareerCreate, db: Session = Depends(get_db)):
    return create_career_service(db, data)


@router.get("/", response_model=list[CareerOut], dependencies=[Depends(get_current_user)])
def list_careers(
    q: str | None = None,
    academic_level: str | None = None,
    status: str | None = None,
    modality: str | None = None,
    faculty: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    items = get_careers_service(db)
    for field, value in (
        ("academic_level", academic_level),
        ("status", status),
        ("modality", modality),
        ("faculty", faculty),
    ):
        if value is not None:
            items = [item for item in items if getattr(item, field) == value]
    return paginate_and_filter(
        items, skip, limit, q, ("code", "name", "description", "degree_title", "faculty")
    )


@router.get("/catalog-options", dependencies=[Depends(career_manager)])
def catalog_options(db: Session = Depends(get_db)):
    return {"faculties": sorted({item.faculty for item in get_careers_service(db) if item.faculty})}


@router.get("/{career_id}/overview", dependencies=[Depends(career_manager)])
def career_overview(career_id: int, version: str | None = None, db: Session = Depends(get_db)):
    from app.models.curriculum_model import CurriculumCourse
    from app.models.section_model import Section
    from app.models.student_model import Student

    career = get_career_service(db, career_id)
    courses = (
        db.query(CurriculumCourse)
        .filter_by(career_id=career_id, curriculum_version=version or career.curriculum_version)
        .all()
    )
    subject_ids = {course.subject_id for course in courses}
    sections = (
        db.query(Section)
        .filter(Section.subject_id.in_(subject_ids))
        .order_by(Section.period_name, Section.code)
        .all()
        if subject_ids
        else []
    )
    return {
        "active_students": db.query(Student).filter_by(career_id=career_id, active=True).count(),
        "total_students": db.query(Student).filter_by(career_id=career_id).count(),
        "sections": [
            {
                "section_id": item.section_id,
                "code": item.code,
                "subject_name": item.subject_name,
                "teacher_name": item.teacher_name,
                "period_name": item.period_name,
                "room": item.room,
                "capacity": item.capacity,
                "status": item.status,
            }
            for item in sections
        ],
    }


@router.get("/{career_id}", response_model=CareerOut, dependencies=[Depends(get_current_user)])
def get_career(career_id: int, db: Session = Depends(get_db)):
    return get_career_service(db, career_id)


@router.patch("/{career_id}", response_model=CareerOut, dependencies=[Depends(career_manager)])
def update_career(career_id: int, data: CareerUpdate, db: Session = Depends(get_db)):
    return update_career_service(db, career_id, data)


@router.delete("/{career_id}", dependencies=[Depends(career_manager)])
def delete_career(career_id: int, db: Session = Depends(get_db)):
    return delete_career_service(db, career_id)
