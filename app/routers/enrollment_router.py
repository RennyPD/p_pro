from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import ensure_enrollment_access, get_current_user, is_admin, require_permissions
from app.db.Session import get_db
from app.models.enrollment_model import Enrollment
from app.models.section_model import Section
from app.models.user_model import User
from app.schemas.enrollment_schema import EnrollmentCreate, EnrollmentOut, EnrollmentUpdate
from app.services.enrollment_service import (
    create_enrollment_service,
    delete_enrollment_service,
    get_enrollment_by_id_service,
    update_enrollment_service,
)

router = APIRouter(prefix="/enrollments", tags=["enrollment"])
enrollment_manager = require_permissions("academic.manage", fallback_roles=("admin",))


@router.post("/", response_model=EnrollmentOut, dependencies=[Depends(enrollment_manager)])
def create_enrollment(enrollment_data: EnrollmentCreate, db: Session = Depends(get_db)):
    return create_enrollment_service(db, enrollment_data)


@router.get("/", response_model=list[EnrollmentOut], dependencies=[Depends(get_current_user)])
def get_enrollments(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Enrollment)
    if not is_admin(user):
        if user.student_id is not None:
            query = query.filter(Enrollment.student_id == user.student_id)
        elif user.teacher_id is not None:
            query = query.join(Enrollment.section).filter(Section.teacher_id == user.teacher_id)
        else:
            return []
    return query.all()


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
