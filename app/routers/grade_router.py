from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import (
    ensure_enrollment_access,
    ensure_section_access,
    get_current_user,
    require_permissions,
)
from app.db.Session import get_db
from app.models.assessment_model import Assessment
from app.models.enrollment_model import Enrollment
from app.models.grade_model import Grade, GradeChange
from app.models.section_model import Section
from app.models.user_model import User
from app.schemas.assessment_schema import ReasonRequest
from app.schemas.grade_schema import (
    GradeBulkCreate,
    GradeChangeOut,
    GradeCreate,
    GradeOut,
    GradeUpdate,
)
from app.services.academic_grading import ensure_grading_open, record_change, write_grade
from app.services.grade_service import get_grade_by_id_service

router = APIRouter(prefix="/grades", tags=["grades"])
grade_manager = require_permissions("grades.manage", fallback_roles=("admin", "teacher"))


def validate_assessment(db: Session, assessment_id: int | None, section_id: int):
    if assessment_id is None:
        return None
    assessment = db.get(Assessment, assessment_id)
    if assessment is None or assessment.section_id != section_id:
        raise HTTPException(status_code=422, detail="Assessment must belong to the section")
    if assessment.closed:
        raise HTTPException(status_code=409, detail="Closed assessments cannot receive changes")
    return assessment


@router.post("/bulk", response_model=list[GradeOut])
def save_section_grades(
    data: GradeBulkCreate, db: Session = Depends(get_db), user: User = Depends(grade_manager)
):
    section = ensure_section_access(db, user, data.section_id)
    ensure_grading_open(db, section)
    ids = [item.enrollment_id for item in data.records]
    if len(set(ids)) != len(ids):
        raise HTTPException(status_code=422, detail="No se puede repetir un estudiante en la carga")
    enrollments = {
        item.enrollment_id: item
        for item in db.query(Enrollment)
        .filter(Enrollment.section_id == data.section_id, Enrollment.enrollment_id.in_(ids))
        .all()
    }
    if len(enrollments) != len(ids):
        raise HTTPException(status_code=422, detail="Every grade must belong to the section")
    assessment = validate_assessment(db, data.assessment_id, section.section_id)
    saved = [
        write_grade(
            db,
            enrollments[item.enrollment_id],
            assessment,
            item.grade_value,
            data.grade_type,
            data.date_recorded,
            data.status,
            user.user_id,
            data.reason,
        )
        for item in data.records
    ]
    db.commit()
    return saved


@router.post("/", response_model=GradeOut)
def create_grade(
    data: GradeCreate, db: Session = Depends(get_db), user: User = Depends(grade_manager)
):
    enrollment = ensure_enrollment_access(db, user, data.enrollment_id)
    ensure_section_access(db, user, enrollment.section_id)
    assessment = validate_assessment(db, data.assessment_id, enrollment.section_id)
    grade = write_grade(
        db,
        enrollment,
        assessment,
        data.grade_value,
        data.grade_type,
        data.date_recorded,
        data.status,
        user.user_id,
        data.reason,
    )
    db.commit()
    return grade


@router.get("/", response_model=list[GradeOut])
def get_grades(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = db.query(Grade).filter(Grade.status != "voided")
    if user.role.name.casefold() != "admin":
        query = query.join(Grade.enrollment)
        if user.student_id is not None:
            query = query.filter(
                Enrollment.student_id == user.student_id, Grade.status == "published"
            )
        elif user.teacher_id is not None:
            query = query.join(Enrollment.section).filter(Section.teacher_id == user.teacher_id)
        else:
            return []
    return query.all()


@router.post("/assessments/{assessment_id}/publish")
def publish_assessment_grades(
    assessment_id: int, db: Session = Depends(get_db), user: User = Depends(grade_manager)
):
    assessment = db.get(Assessment, assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    ensure_section_access(db, user, assessment.section_id)
    ensure_grading_open(db, assessment.section)
    if assessment.closed:
        raise HTTPException(status_code=409, detail="La evaluación está cerrada")
    grades = (
        db.query(Grade)
        .join(Grade.enrollment)
        .filter(
            Grade.assessment_id == assessment_id,
            Grade.status == "draft",
            Enrollment.state.in_(("enrolled", "completed", "failed")),
        )
        .all()
    )
    for grade in grades:
        grade.status = "published"
        record_change(
            db,
            grade,
            user.user_id,
            "Publicación de resultados",
            grade.grade_value,
            "draft",
            "published",
        )
    db.commit()
    return {"published": len(grades)}


@router.get("/{grade_id}/history", response_model=list[GradeChangeOut])
def grade_history(
    grade_id: int, db: Session = Depends(get_db), user: User = Depends(grade_manager)
):
    grade = get_grade_by_id_service(db, grade_id)
    ensure_section_access(db, user, grade.enrollment.section_id)
    history = (
        db.query(GradeChange)
        .filter_by(grade_id=grade_id)
        .order_by(GradeChange.changed_at.desc(), GradeChange.grade_change_id.desc())
        .all()
    )
    return [
        GradeChangeOut.model_validate(item).model_copy(
            update={"changed_by_name": db.get(User, item.changed_by).username}
        )
        for item in history
    ]


@router.get("/{grade_id}", response_model=GradeOut)
def get_grade_by_id(
    grade_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    grade = get_grade_by_id_service(db, grade_id)
    ensure_enrollment_access(db, user, grade.enrollment_id)
    if grade.status == "voided" or (user.student_id is not None and grade.status != "published"):
        raise HTTPException(status_code=404, detail="Grade not found")
    return grade


@router.patch("/{grade_id}", response_model=GradeOut)
def update_grade(
    grade_id: int,
    data: GradeUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(grade_manager),
):
    grade = get_grade_by_id_service(db, grade_id)
    ensure_section_access(db, user, grade.enrollment.section_id)
    values = data.model_dump(exclude_unset=True)
    for field in ("enrollment_id", "assessment_id"):
        if field in values and values[field] != getattr(grade, field):
            raise HTTPException(
                status_code=422,
                detail="No se puede trasladar una nota a otro estudiante o evaluación",
            )
    for field in ("grade_value", "grade_type", "date_recorded", "status"):
        if field in values and values[field] is None:
            raise HTTPException(status_code=422, detail="Los campos de la nota no pueden ser nulos")
    assessment = validate_assessment(db, grade.assessment_id, grade.enrollment.section_id)
    write_grade(
        db,
        grade.enrollment,
        assessment,
        values.get("grade_value", grade.grade_value),
        values.get("grade_type", grade.grade_type),
        values.get("date_recorded", grade.date_recorded),
        values.get("status", grade.status),
        user.user_id,
        data.reason,
        grade,
    )
    db.commit()
    return grade


@router.delete("/{grade_id}")
def delete_grade(
    grade_id: int,
    data: ReasonRequest,
    db: Session = Depends(get_db),
    user: User = Depends(grade_manager),
):
    grade = get_grade_by_id_service(db, grade_id)
    ensure_section_access(db, user, grade.enrollment.section_id)
    ensure_grading_open(db, grade.enrollment.section, grade.enrollment)
    validate_assessment(db, grade.assessment_id, grade.enrollment.section_id)
    previous = grade.status
    grade.status = "voided"
    record_change(db, grade, user.user_id, data.reason, grade.grade_value, previous, "voided")
    db.commit()
    return {"message": "Nota anulada; historial conservado"}
