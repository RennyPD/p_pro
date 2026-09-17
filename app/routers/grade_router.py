from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import ensure_enrollment_access, get_current_user, is_admin, require_roles
from app.db.Session import get_db
from app.models.enrollment_model import Enrollment
from app.models.grade_model import Grade
from app.models.section_model import Section
from app.models.user_model import User
from app.schemas.grade_schema import GradeBulkCreate, GradeCreate, GradeOut, GradeUpdate
from app.services.grade_service import (
    create_grade_service,
    delete_grade_service,
    get_grade_by_id_service,
    update_grade_service,
)

router = APIRouter(prefix="/grades", tags=["grades"])


@router.post("/bulk", response_model=list[GradeOut])
def save_section_grades(
    data: GradeBulkCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "teacher")),
):
    from fastapi import HTTPException

    enrollment_ids = {item.enrollment_id for item in data.records}
    enrollments = (
        db.query(Enrollment)
        .filter(
            Enrollment.section_id == data.section_id,
            Enrollment.enrollment_id.in_(enrollment_ids),
        )
        .all()
    )
    if len(enrollments) != len(enrollment_ids):
        raise HTTPException(status_code=422, detail="Every grade must belong to the section")
    if enrollments and not is_admin(user) and user.teacher_id != enrollments[0].section.teacher_id:
        raise HTTPException(
            status_code=403, detail="Only the assigned teacher can grade this section"
        )
    saved = []
    for item in data.records:
        grade = (
            db.query(Grade)
            .filter(
                Grade.enrollment_id == item.enrollment_id,
                Grade.grade_type == data.grade_type,
            )
            .first()
        )
        if grade is None:
            grade = Grade(enrollment_id=item.enrollment_id, grade_type=data.grade_type)
            db.add(grade)
        grade.grade_value = item.grade_value
        grade.date_recorded = data.date_recorded
        saved.append(grade)
    db.commit()
    for grade in saved:
        db.refresh(grade)
    return saved


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
