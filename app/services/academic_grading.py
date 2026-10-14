"""One published result for records, curriculum, eligibility and dashboards."""

from dataclasses import dataclass
from datetime import UTC, date, datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.assessment_model import Assessment
from app.models.configuration_model import AcademicPeriod, InstitutionSettings
from app.models.enrollment_model import Enrollment
from app.models.grade_model import Grade, GradeChange
from app.models.security_model import AuditLog


@dataclass
class AcademicResult:
    value: float | None
    completed_weight: float
    configured_weight: float
    final: bool
    status: str
    mode: str


def academic_result(db: Session, enrollment: Enrollment) -> AcademicResult:
    assessments = db.query(Assessment).filter_by(section_id=enrollment.section_id).all()
    published = [grade for grade in enrollment.grades if grade.status == "published"]
    settings = db.get(InstitutionSettings, 1)
    passing = (
        enrollment.passing_grade
        if enrollment.passing_grade is not None
        else settings.passing_grade
        if settings
        else 70
    )
    if enrollment.state in {"withdrawn", "waitlisted"}:
        return AcademicResult(
            None, 0, 0, False, enrollment.state, "weighted" if assessments else "legacy"
        )
    if assessments:
        grades = {grade.assessment_id: grade.grade_value for grade in published}
        configured = sum(item.weight for item in assessments)
        completed = sum(item.weight for item in assessments if item.assessment_id in grades)
        value = (
            round(
                sum(grades.get(item.assessment_id, 0) * item.weight / 100 for item in assessments),
                2,
            )
            if completed
            else None
        )
        final = abs(configured - 100) < 0.001 and all(
            item.closed and item.assessment_id in grades for item in assessments
        )
        mode = "weighted"
    else:
        # Preserve existing historical unweighted results; never include drafts.
        values = [grade.grade_value for grade in published if grade.assessment_id is None]
        value = round(sum(values) / len(values), 2) if values else None
        final = bool(values)
        completed = configured = 100 if values else 0
        mode = "legacy"
    status = "in_progress" if not final else "passed" if value >= passing else "failed"
    return AcademicResult(value, completed, configured, final, status, mode)


def ensure_grading_open(
    db: Session, section, enrollment: Enrollment | None = None, allow_closed_section: bool = False
):
    if section.status == "cancelled" or (section.status == "closed" and not allow_closed_section):
        raise HTTPException(status_code=409, detail="La sección está cerrada o cancelada")
    names = {section.period_name}
    if enrollment:
        names.add(enrollment.period)
    else:
        names.update(
            item.period
            for item in section.enrollments
            if item.state in {"enrolled", "completed", "failed"}
        )
    for period in db.query(AcademicPeriod).filter(AcademicPeriod.name.in_(names - {""})).all():
        if period.status == "closed" or (
            period.grading_deadline and date.today() > period.grading_deadline
        ):
            raise HTTPException(
                status_code=409,
                detail="El período está cerrado o venció el plazo de calificación. Requiere reapertura administrativa.",
            )


def audit_event(db: Session, user_id: int, action: str, resource: str, detail: str):
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            resource=resource,
            detail=detail[:500],
            created_at=datetime.now(UTC).replace(tzinfo=None),
        )
    )


def record_change(
    db: Session,
    grade: Grade,
    user_id: int,
    reason: str,
    previous_value: float | None,
    previous_status: str | None,
    action: str,
):
    db.flush()
    db.add(
        GradeChange(
            grade_id=grade.grade_id,
            previous_value=previous_value,
            new_value=grade.grade_value,
            changed_by=user_id,
            reason=reason,
            previous_status=previous_status,
            new_status=grade.status,
            action=action,
        )
    )
    grade.updated_by = user_id
    grade.updated_at = datetime.now(UTC).replace(tzinfo=None)


def write_grade(
    db: Session,
    enrollment: Enrollment,
    assessment: Assessment | None,
    value: float,
    grade_type: str,
    recorded: str,
    state: str,
    user_id: int,
    reason: str,
    existing: Grade | None = None,
):
    if enrollment.state in {"waitlisted", "withdrawn"}:
        raise HTTPException(
            status_code=409, detail="Solo se califican estudiantes inscritos activos"
        )
    ensure_grading_open(db, enrollment.section, enrollment)
    if (
        assessment is None
        and db.query(Assessment).filter_by(section_id=enrollment.section_id).first()
    ):
        raise HTTPException(
            status_code=422,
            detail="Esta sección tiene un plan ponderado. Registra la nota en una de sus evaluaciones, no como nota independiente.",
        )
    if assessment and assessment.closed:
        raise HTTPException(status_code=409, detail="La evaluación está cerrada")
    query = db.query(Grade).filter_by(
        enrollment_id=enrollment.enrollment_id,
        assessment_id=assessment.assessment_id if assessment else None,
    )
    if assessment is None:
        query = query.filter_by(grade_type=grade_type)
    grade = existing or query.first()
    previous_value, previous_status = (grade.grade_value, grade.status) if grade else (None, None)
    previous_date = grade.date_recorded if grade else None
    previous_type = grade.grade_type if grade else None
    if grade is None:
        grade = Grade(
            enrollment_id=enrollment.enrollment_id,
            assessment_id=assessment.assessment_id if assessment else None,
        )
        db.add(grade)
    grade.grade_type = assessment.name if assessment else grade_type
    grade.grade_value, grade.date_recorded, grade.status = value, recorded, state
    if (
        previous_value != value
        or previous_status != state
        or previous_date != recorded
        or previous_type != grade.grade_type
    ):
        record_change(
            db,
            grade,
            user_id,
            reason,
            previous_value,
            previous_status,
            "created" if previous_value is None else "updated",
        )
    return grade
