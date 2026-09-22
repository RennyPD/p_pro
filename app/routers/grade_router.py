from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import (
    ensure_enrollment_access,
    ensure_section_access,
    get_current_user,
    is_admin,
    require_permissions,
)
from app.db.Session import get_db
from app.models.assessment_model import Assessment
from app.models.enrollment_model import Enrollment
from app.models.grade_model import Grade, GradeChange
from app.models.section_model import Section
from app.models.user_model import User
from app.schemas.grade_schema import (
    GradeBulkCreate,
    GradeChangeOut,
    GradeCreate,
    GradeOut,
    GradeUpdate,
)
from app.services.grade_service import (
    create_grade_service,
    delete_grade_service,
    get_grade_by_id_service,
    update_grade_service,
)

router = APIRouter(prefix="/grades", tags=["grades"])
grade_manager = require_permissions("grades.manage", fallback_roles=("admin", "teacher"))


def validate_assessment(
    db: Session, assessment_id: int | None, section_id: int
) -> Assessment | None:
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
    data: GradeBulkCreate,
    db: Session = Depends(get_db),
    user: User = Depends(grade_manager),
):
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
    assessment = validate_assessment(db, data.assessment_id, data.section_id)
    grade_type = assessment.name if assessment else data.grade_type
    saved = []
    for item in data.records:
        grade = (
            db.query(Grade)
            .filter(
                Grade.enrollment_id == item.enrollment_id,
                Grade.assessment_id == data.assessment_id,
                Grade.grade_type == grade_type,
            )
            .first()
        )
        previous = grade.grade_value if grade is not None else None
        if grade is None:
            grade = Grade(
                enrollment_id=item.enrollment_id,
                assessment_id=data.assessment_id,
                grade_type=grade_type,
            )
            db.add(grade)
        grade.grade_value = item.grade_value
        grade.date_recorded = data.date_recorded
        grade.status = data.status
        grade.updated_by = user.user_id
        grade.updated_at = datetime.now(UTC).replace(tzinfo=None)
        db.flush()
        if previous != item.grade_value:
            db.add(
                GradeChange(
                    grade_id=grade.grade_id,
                    previous_value=previous,
                    new_value=item.grade_value,
                    changed_by=user.user_id,
                    reason=data.reason,
                )
            )
        saved.append(grade)
    db.commit()
    for grade in saved:
        db.refresh(grade)
    return saved


@router.post("/", response_model=GradeOut, dependencies=[Depends(grade_manager)])
def create_grade(
    grade_data: GradeCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    enrollment = ensure_enrollment_access(db, user, grade_data.enrollment_id)
    if not is_admin(user) and user.teacher_id != enrollment.section.teacher_id:
        raise HTTPException(
            status_code=403, detail="Only the assigned teacher can grade this enrollment"
        )
    assessment = validate_assessment(db, grade_data.assessment_id, enrollment.section_id)
    if assessment:
        grade_data = grade_data.model_copy(update={"grade_type": assessment.name})
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
    updated = (
        db.query(Grade)
        .filter(Grade.assessment_id == assessment_id)
        .update(
            {
                Grade.status: "published",
                Grade.updated_by: user.user_id,
                Grade.updated_at: datetime.now(UTC).replace(tzinfo=None),
            },
            synchronize_session=False,
        )
    )
    db.commit()
    return {"published": updated}


@router.get("/{grade_id}/history", response_model=list[GradeChangeOut])
def grade_history(
    grade_id: int, db: Session = Depends(get_db), user: User = Depends(grade_manager)
):
    grade = get_grade_by_id_service(db, grade_id)
    ensure_enrollment_access(db, user, grade.enrollment_id)
    return (
        db.query(GradeChange)
        .filter_by(grade_id=grade_id)
        .order_by(GradeChange.changed_at.desc())
        .all()
    )


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
    dependencies=[Depends(grade_manager)],
)
def update_grade(
    grade_id: int,
    grade_data: GradeUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    grade = get_grade_by_id_service(db, grade_id)
    enrollment = ensure_enrollment_access(db, user, grade.enrollment_id)
    if grade.assessment and grade.assessment.closed:
        raise HTTPException(status_code=409, detail="Closed assessments cannot receive changes")
    if not is_admin(user) and user.teacher_id != enrollment.section.teacher_id:
        raise HTTPException(
            status_code=403, detail="Only the assigned teacher can update this grade"
        )
    return update_grade_service(db, grade_id, grade_data)


@router.delete("/{grade_id}", dependencies=[Depends(grade_manager)])
def delete_grade(
    grade_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    grade = get_grade_by_id_service(db, grade_id)
    enrollment = ensure_enrollment_access(db, user, grade.enrollment_id)
    if grade.assessment and grade.assessment.closed:
        raise HTTPException(status_code=409, detail="Closed assessments cannot receive changes")
    if not is_admin(user) and user.teacher_id != enrollment.section.teacher_id:
        raise HTTPException(
            status_code=403, detail="Only the assigned teacher can delete this grade"
        )
    return delete_grade_service(db, grade_id)
