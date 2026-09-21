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
from app.models.configuration_model import InstitutionSettings
from app.models.enrollment_model import Enrollment
from app.models.user_model import User
from app.schemas.assessment_schema import (
    AssessmentCreate,
    AssessmentOut,
    AssessmentUpdate,
    FinalGradeOut,
)

router = APIRouter(prefix="/assessments", tags=["weighted assessments"])
assessment_manager = require_permissions("grades.manage", fallback_roles=("admin", "teacher"))


def ensure_assessment_writer(db: Session, user: User, assessment: Assessment) -> None:
    ensure_section_access(db, user, assessment.section_id)


def validate_total_weight(
    db: Session, section_id: int, weight: float, exclude_id: int | None = None
) -> None:
    query = db.query(Assessment).filter(Assessment.section_id == section_id)
    if exclude_id is not None:
        query = query.filter(Assessment.assessment_id != exclude_id)
    total = sum(item.weight for item in query.all()) + weight
    if total > 100.001:
        raise HTTPException(status_code=422, detail="Assessment weights cannot exceed 100%")


@router.get("/sections/{section_id}", response_model=list[AssessmentOut])
def list_assessments(
    section_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_section_access(db, user, section_id, allow_student=True)
    return (
        db.query(Assessment)
        .filter(Assessment.section_id == section_id)
        .order_by(Assessment.due_date, Assessment.assessment_id)
        .all()
    )


@router.post("/", response_model=AssessmentOut)
def create_assessment(
    data: AssessmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(assessment_manager),
):
    ensure_section_access(db, user, data.section_id)
    validate_total_weight(db, data.section_id, data.weight)
    assessment = Assessment(**data.model_dump())
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return assessment


@router.patch("/{assessment_id}", response_model=AssessmentOut)
def update_assessment(
    assessment_id: int,
    data: AssessmentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(assessment_manager),
):
    assessment = db.get(Assessment, assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    ensure_assessment_writer(db, user, assessment)
    if assessment.closed:
        raise HTTPException(status_code=409, detail="Closed assessments cannot be modified")
    values = data.model_dump(exclude_unset=True)
    if "weight" in values:
        validate_total_weight(db, assessment.section_id, values["weight"], assessment_id)
    for key, value in values.items():
        setattr(assessment, key, value)
    db.commit()
    db.refresh(assessment)
    return assessment


@router.post("/{assessment_id}/close", response_model=AssessmentOut)
def close_assessment(
    assessment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(assessment_manager),
):
    assessment = db.get(Assessment, assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    ensure_assessment_writer(db, user, assessment)
    enrollment_count = (
        db.query(Enrollment).filter(Enrollment.section_id == assessment.section_id).count()
    )
    if enrollment_count and len(assessment.grades) < enrollment_count:
        raise HTTPException(
            status_code=409,
            detail="Every enrolled student must have a grade before closing the assessment",
        )
    assessment.closed = True
    db.commit()
    db.refresh(assessment)
    return assessment


@router.post("/{assessment_id}/reopen", response_model=AssessmentOut)
def reopen_assessment(
    assessment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(assessment_manager),
):
    assessment = db.get(Assessment, assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    if not is_admin(user):
        raise HTTPException(status_code=403, detail="Only an admin can reopen an assessment")
    assessment.closed = False
    db.commit()
    db.refresh(assessment)
    return assessment


def final_grade(db: Session, enrollment: Enrollment) -> FinalGradeOut:
    assessments = db.query(Assessment).filter(Assessment.section_id == enrollment.section_id).all()
    grades = {grade.assessment_id: grade.grade_value for grade in enrollment.grades}
    weighted = sum(grades.get(item.assessment_id, 0) * item.weight / 100 for item in assessments)
    completed_weight = sum(item.weight for item in assessments if item.assessment_id in grades)
    configured_weight = sum(item.weight for item in assessments)
    is_final = (
        bool(assessments)
        and abs(configured_weight - 100) < 0.001
        and all(item.closed for item in assessments)
    )
    settings = db.get(InstitutionSettings, 1)
    passing = settings.passing_grade if settings else 70.0
    if not is_final:
        status = "in_progress"
    elif weighted >= passing:
        status = "passed"
    else:
        status = "failed"
    return FinalGradeOut(
        enrollment_id=enrollment.enrollment_id,
        student_id=enrollment.student_id,
        student_name=f"{enrollment.student.first_name} {enrollment.student.last_name}",
        weighted_grade=round(weighted, 2),
        completed_weight=round(completed_weight, 2),
        final=is_final,
        status=status,
    )


@router.get("/enrollments/{enrollment_id}/final", response_model=FinalGradeOut)
def enrollment_final_grade(
    enrollment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    enrollment = ensure_enrollment_access(db, user, enrollment_id)
    return final_grade(db, enrollment)


@router.get("/sections/{section_id}/finals", response_model=list[FinalGradeOut])
def section_final_grades(
    section_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_section_access(db, user, section_id)
    enrollments = db.query(Enrollment).filter(Enrollment.section_id == section_id).all()
    return [final_grade(db, item) for item in enrollments]
