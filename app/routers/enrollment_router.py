from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import false, or_
from sqlalchemy.orm import Session, joinedload

from app.auth import (
    ACADEMIC_SCOPE,
    ensure_enrollment_access,
    get_current_user,
    has_scope,
    require_permissions,
)
from app.db.Session import get_db
from app.models.enrollment_model import Enrollment
from app.models.section_model import Section
from app.models.student_model import Student
from app.models.subject_model import Subject
from app.models.user_model import User
from app.pagination import page_query
from app.schemas.enrollment_schema import EnrollmentCreate, EnrollmentOut, EnrollmentUpdate
from app.services.enrollment_service import (
    create_enrollment_service,
    delete_enrollment_service,
    get_enrollment_by_id_service,
    update_enrollment_service,
)

router = APIRouter(prefix="/enrollments", tags=["enrollment"])
enrollment_manager = require_permissions("enrollments.manage")


@router.post("/", response_model=EnrollmentOut, dependencies=[Depends(enrollment_manager)])
def create_enrollment(enrollment_data: EnrollmentCreate, db: Session = Depends(get_db)):
    return create_enrollment_service(db, enrollment_data)


@router.get("/", response_model=list[EnrollmentOut], dependencies=[Depends(get_current_user)])
def get_enrollments(
    response: Response,
    q: str | None = None,
    period: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int | None = Query(None, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = (
        db.query(Enrollment)
        .join(Enrollment.section)
        .options(
            joinedload(Enrollment.student),
            joinedload(Enrollment.section).joinedload(Section.subject),
        )
    )
    if not has_scope(user, *ACADEMIC_SCOPE):
        if user.student_id is not None:
            query = query.filter(Enrollment.student_id == user.student_id)
        elif user.teacher_id is not None:
            query = query.filter(Section.teacher_id == user.teacher_id)
        else:
            query = query.filter(false())
    if period:
        query = query.filter(Enrollment.period.icontains(period.strip(), autoescape=True))
    if q and (term := q.strip()):
        query = (
            query.join(Enrollment.student)
            .join(Section.subject)
            .filter(
                or_(
                    Enrollment.period.icontains(term, autoescape=True),
                    Student.enrollment_number.icontains(term, autoescape=True),
                    (Student.first_name + " " + Student.last_name).icontains(term, autoescape=True),
                    Section.code.icontains(term, autoescape=True),
                    Subject.code.icontains(term, autoescape=True),
                    Subject.description.icontains(term, autoescape=True),
                )
            )
        )
    return page_query(query.order_by(Enrollment.enrollment_id), response, skip, limit)


@router.get(
    "/{enrollment_id}", response_model=EnrollmentOut, dependencies=[Depends(get_current_user)]
)
def get_enrollment_by_id(
    enrollment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    enrollment = get_enrollment_by_id_service(db, enrollment_id)
    ensure_enrollment_access(db, user, enrollment_id)
    return enrollment


@router.patch(
    "/{enrollment_id}", response_model=EnrollmentOut, dependencies=[Depends(enrollment_manager)]
)
def update_enrollment(
    enrollment_id: int, enrollment_data: EnrollmentUpdate, db: Session = Depends(get_db)
):
    return update_enrollment_service(db, enrollment_id, enrollment_data)


@router.delete("/{enrollment_id}", dependencies=[Depends(enrollment_manager)])
def delete_enrollment(enrollment_id: int, db: Session = Depends(get_db)):
    return delete_enrollment_service(db, enrollment_id)
