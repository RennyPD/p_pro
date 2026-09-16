from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import ensure_enrollment_access, get_current_user, is_admin, require_roles
from app.db.Session import get_db
from app.models.enrollment_model import Enrollment
from app.models.grade_model import Grade
from app.models.section_model import Section
from app.models.user_model import User
from app.schemas.grade_schema import GradeCreate, GradeOut, GradeUpdate
from app.services.grade_service import (
    create_grade_service,
    delete_grade_service,
    get_grade_by_id_service,
    update_grade_service,
)

router = APIRouter(prefix="/grades", tags=["grades"])


@router.post(
    "/", response_model=GradeOut, dependencies=[Depends(require_roles("admin", "teacher"))]
)
def create_grade(
    grade_data: GradeCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    enrollment = ensure_enrollment_access(db, user, grade_data.enrollment_id)
    if not is_admin(user) and user.teacher_id != enrollment.section.teacher_id:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=403, detail="Only the assigned teacher can grade this enrollment"
        )
    return create_grade_service(db, grade_data)


@router.get("/", response_model=list[GradeOut], dependencies=[Depends(get_current_user)])
def get_grades(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Grade)
    if not is_admin(user):
        query = query.join(Grade.enrollment)
        if user.student_id is not None:
            query = query.filter(Enrollment.student_id == user.student_id)
        elif user.teacher_id is not None:
            query = query.join(Enrollment.section).filter(Section.teacher_id == user.teacher_id)
        else:
            return []
    return query.all()


@router.get("/{grade_id}", response_model=GradeOut, dependencies=[Depends(get_current_user)])
def get_grade_by_id(
    grade_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    grade = get_grade_by_id_service(db, grade_id)
    ensure_enrollment_access(db, user, grade.enrollment_id)
    return grade


@router.patch(
    "/{grade_id}",
    response_model=GradeOut,
    dependencies=[Depends(require_roles("admin", "teacher"))],
)
def update_grade(
    grade_id: int,
    grade_data: GradeUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    grade = get_grade_by_id_service(db, grade_id)
    enrollment = ensure_enrollment_access(db, user, grade.enrollment_id)
    if not is_admin(user) and user.teacher_id != enrollment.section.teacher_id:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=403, detail="Only the assigned teacher can update this grade"
        )
    return update_grade_service(db, grade_id, grade_data)


@router.delete("/{grade_id}", dependencies=[Depends(require_roles("admin", "teacher"))])
def delete_grade(
    grade_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    grade = get_grade_by_id_service(db, grade_id)
    enrollment = ensure_enrollment_access(db, user, grade.enrollment_id)
    if not is_admin(user) and user.teacher_id != enrollment.section.teacher_id:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=403, detail="Only the assigned teacher can delete this grade"
        )
    return delete_grade_service(db, grade_id)
