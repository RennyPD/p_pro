from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import ensure_student_academic_access, get_current_user, is_admin, require_permissions
from app.db.Session import get_db
from app.models.enrollment_model import Enrollment
from app.models.section_model import Section
from app.models.student_model import Student
from app.models.user_model import User
from app.pagination import paginate_and_filter
from app.schemas.student_schema import StudentCreate, StudentOut, StudentUpdate
from app.services.student_service import (
    create_student_service,
    delete_student_service,
    get_student_by_id_service,
    update_student_service,
)

router = APIRouter(prefix="/students", tags=["students"])
student_manager = require_permissions("academic.manage", fallback_roles=("admin",))


@router.post("/", response_model=StudentOut, dependencies=[Depends(student_manager)])
def create_student(student_data: StudentCreate, db: Session = Depends(get_db)):
    return create_student_service(db, student_data)


@router.get("/", response_model=list[StudentOut], dependencies=[Depends(get_current_user)])
def get_students(
    q: str | None = None,
    career_id: int | None = None,
    active: bool | None = None,
    hold: str | None = Query(None, pattern="^(academic|financial|clear)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Student)
    if career_id is not None:
        query = query.filter(Student.career_id == career_id)
    if active is not None:
        query = query.filter(Student.active == active)
    if hold == "academic":
        query = query.filter(Student.academic_hold.is_(True))
    elif hold == "financial":
        query = query.filter(Student.financial_hold.is_(True))
    elif hold == "clear":
        query = query.filter(Student.academic_hold.is_(False), Student.financial_hold.is_(False))
    if is_admin(user):
        return paginate_and_filter(
            query.order_by(Student.last_name, Student.first_name).all(),
            skip,
            limit,
            q,
            ("full_name", "email", "enrollment_number", "document_number"),
        )
    if user.student_id is not None:
        query = query.filter(Student.student_id == user.student_id)
    elif user.teacher_id is not None:
        query = (
            query.join(Student.enrollments)
            .join(Enrollment.section)
            .filter(Section.teacher_id == user.teacher_id)
            .distinct()
        )
    else:
        return []
    return paginate_and_filter(
        query.order_by(Student.last_name, Student.first_name).all(),
        skip,
        limit,
        q,
        ("full_name", "email", "enrollment_number", "document_number"),
    )


@router.get("/{student_id}", response_model=StudentOut, dependencies=[Depends(get_current_user)])
def get_student_by_id(
    student_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):

    ensure_student_academic_access(db, user, student_id)
    return get_student_by_id_service(db, student_id)


@router.patch("/{student_id}", response_model=StudentOut, dependencies=[Depends(student_manager)])
def update_student(student_id: int, student_data: StudentUpdate, db: Session = Depends(get_db)):
    return update_student_service(db, student_id, student_data)


@router.delete("/{student_id}", dependencies=[Depends(student_manager)])
def delete_student(student_id: int, db: Session = Depends(get_db)):
    return delete_student_service(db, student_id)
