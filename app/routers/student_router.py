from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import ensure_student_academic_access, get_current_user, is_admin, require_roles
from app.db.Session import get_db
from app.models.enrollment_model import Enrollment
from app.models.section_model import Section
from app.models.student_model import Student
from app.models.user_model import User
from app.schemas.student_schema import StudentCreate, StudentOut, StudentUpdate
from app.services.student_service import (
    create_student_service,
    delete_student_service,
    get_student_by_id_service,
    update_student_service,
)

router = APIRouter(prefix="/students", tags=["students"])


@router.post("/", response_model=StudentOut, dependencies=[Depends(require_roles("admin"))])
def create_student(student_data: StudentCreate, db: Session = Depends(get_db)):
    return create_student_service(db, student_data)


@router.get("/", response_model=list[StudentOut], dependencies=[Depends(get_current_user)])
def get_students(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Student)
    if is_admin(user):
        return query.all()
    if user.student_id is not None:
        return query.filter(Student.student_id == user.student_id).all()
    if user.teacher_id is not None:
        return (
            query.join(Student.enrollments)
            .join(Enrollment.section)
            .filter(Section.teacher_id == user.teacher_id)
            .distinct()
            .all()
        )
    return []


@router.get("/{student_id}", response_model=StudentOut, dependencies=[Depends(get_current_user)])
def get_student_by_id(
    student_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):

    ensure_student_academic_access(db, user, student_id)
    return get_student_by_id_service(db, student_id)


@router.patch(
    "/{student_id}", response_model=StudentOut, dependencies=[Depends(require_roles("admin"))]
)
def update_student(student_id: int, student_data: StudentUpdate, db: Session = Depends(get_db)):
    return update_student_service(db, student_id, student_data)


@router.delete("/{student_id}", dependencies=[Depends(require_roles("admin"))])
def delete_student(student_id: int, db: Session = Depends(get_db)):
    return delete_student_service(db, student_id)
