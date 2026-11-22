"""Detail a guardian sees of each linked student (audit A1, M8).

Every route checks that the student is linked to the guardian account and that
the link allows the area (``ensure_guardian_view``). By default a guardian sees
everything; the institution restricts single links from the student's record.
"""

from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.auth import ensure_guardian_view, require_personal
from app.db.Session import get_db
from app.models.assessment_model import Assessment
from app.models.configuration_model import AcademicPeriod
from app.models.enrollment_model import Enrollment
from app.models.operations_model import Assignment, EarlyAlert, Submission
from app.models.section_model import Section
from app.models.subject_model import Subject
from app.models.user_model import User
from app.pagination import page_query
from app.schemas.academic_schema import AttendanceCourseSummary, RosterAttendanceItem
from app.schemas.finance_schema import AccountStatement
from app.schemas.guardian_schema import (
    GuardianAlert,
    GuardianAssessment,
    GuardianAttendance,
    GuardianCourseGrades,
    GuardianFinance,
    GuardianGrades,
    GuardianPerformance,
    GuardianPeriodPerformance,
    GuardianTask,
)
from app.services.academic_grading import academic_result
from app.services.academic_metrics import summarize_results
from app.services.account_statement import account_statement
from app.services.finance_workflow import get_account, summary, upcoming_due

router = APIRouter(prefix="/guardian", tags=["guardian portal"])
guardian = require_personal("records.own", "linked")
VISIBLE_STATES = ("enrolled", "completed", "failed")
STATUSES = ("present", "absent", "late", "excused", "early_departure")


def period_name(db: Session, period: str | None) -> str | None:
    if period:
        return period
    active = db.query(AcademicPeriod).filter_by(active=True).first()
    return active.name if active else None


def enrollments_of(db: Session, student_id: int, period: str | None):
    query = db.query(Enrollment).filter(
        Enrollment.student_id == student_id, Enrollment.state.in_(VISIBLE_STATES)
    )
    if period:
        query = query.filter(Enrollment.period == period)
    return query.order_by(Enrollment.enrollment_id).all()


def percentage(part: int, total: int) -> float | None:
    return round(part * 100 / total, 2) if total else None


@router.get("/students/{student_id}/attendance", response_model=GuardianAttendance)
def attendance(
    student_id: int,
    period: str | None = None,
    start: date | None = None,
    end: date | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(guardian),
):
    ensure_guardian_view(db, user, student_id, "attendance")
    if start and end and start > end:
        raise HTTPException(422, "El inicio debe ser anterior al fin")
    period = period_name(db, period)
    courses, totals = [], dict.fromkeys(STATUSES, 0)
    for item in enrollments_of(db, student_id, period):
        records = sorted(
            (
                r
                for r in item.attendances
                if (not start or r.date.date() >= start) and (not end or r.date.date() <= end)
            ),
            key=lambda r: r.date,
            reverse=True,
        )
        counts = {status: sum(r.status == status for r in records) for status in STATUSES}
        for status, count in counts.items():
            totals[status] += count
        present = sum(r.present for r in records)
        courses.append(
            AttendanceCourseSummary(
                section_id=item.section_id,
                section_code=item.section.code,
                subject_code=item.section.subject.code,
                subject_name=item.section.subject.description,
                present_count=present,
                total_count=len(records),
                percentage=percentage(present, len(records)),
                enrollment_id=item.enrollment_id,
                period=item.period,
                state=item.state,
                counts=counts,
                records=[
                    RosterAttendanceItem(
                        attendance_id=r.attendance_id,
                        date=r.date.date(),
                        status=r.status,
                        note=r.note,
                        excuse_reference=r.excuse_reference,
                    )
                    for r in records
                ],
            )
        )
    present = sum(course.present_count for course in courses)
    total = sum(course.total_count for course in courses)
    return GuardianAttendance(
        student_id=student_id,
        period=period,
        present_count=present,
        total_count=total,
        percentage=percentage(present, total),
        counts=totals,
        courses=courses,
    )


@router.get("/students/{student_id}/grades", response_model=GuardianGrades)
def grades(
    student_id: int,
    period: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(guardian),
):
    """Published grades only, per subject and assessment."""
    ensure_guardian_view(db, user, student_id, "academic")
    period = period_name(db, period)
    courses = []
    for item in enrollments_of(db, student_id, period):
        result = academic_result(db, item)
        published = [grade for grade in item.grades if grade.status == "published"]
        by_assessment = {grade.assessment_id: grade for grade in published}
        assessments = [
            GuardianAssessment(
                assessment_id=assessment.assessment_id,
                name=assessment.name,
                weight=assessment.weight,
                due_date=assessment.due_date,
                grade_value=grade.grade_value if grade else None,
                contribution=round(grade.grade_value * assessment.weight / 100, 2)
                if grade
                else None,
            )
            for assessment in db.query(Assessment)
            .filter_by(section_id=item.section_id)
            .order_by(Assessment.due_date.is_(None), Assessment.due_date, Assessment.assessment_id)
            for grade in [by_assessment.get(assessment.assessment_id)]
        ]
        if not assessments:
            assessments = [
                GuardianAssessment(
                    assessment_id=None,
                    name=grade.grade_type,
                    weight=None,
                    due_date=grade.date_recorded,
                    grade_value=grade.grade_value,
                    contribution=None,
                )
                for grade in published
            ]
        courses.append(
            GuardianCourseGrades(
                enrollment_id=item.enrollment_id,
                section_code=item.section.code,
                subject_code=item.section.subject.code,
                subject_name=item.section.subject.description,
                state=item.state,
                result=result.value,
                result_status=result.status,
                final=result.final,
                completed_weight=result.completed_weight,
                configured_weight=result.configured_weight,
                assessments=assessments,
            )
        )
    return GuardianGrades(student_id=student_id, period=period, courses=courses)


@router.get("/students/{student_id}/tasks", response_model=list[GuardianTask])
def tasks(
    student_id: int,
    response: Response,
    status: str | None = Query(None, pattern="^(pending|overdue|submitted|graded)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(guardian),
):
    """Published tasks of the student's sections with the student's own submission."""
    ensure_guardian_view(db, user, student_id, "tasks")
    now = datetime.now(UTC).replace(tzinfo=None)
    sections = db.query(Enrollment.section_id).filter(
        Enrollment.student_id == student_id, Enrollment.state.in_(VISIBLE_STATES)
    )
    query = (
        db.query(Assignment, Submission, Section, Subject)
        .join(Section, Section.section_id == Assignment.section_id)
        .join(Subject, Subject.subject_id == Section.subject_id)
        .outerjoin(
            Submission,
            and_(
                Submission.assignment_id == Assignment.assignment_id,
                Submission.student_id == student_id,
            ),
        )
        .filter(Assignment.published.is_(True), Assignment.section_id.in_(sections))
    )
    if status == "graded":
        query = query.filter(Submission.status == "graded")
    elif status == "submitted":
        query = query.filter(Submission.submission_id.is_not(None), Submission.status != "graded")
    elif status == "overdue":
        query = query.filter(Submission.submission_id.is_(None), Assignment.due_at < now)
    elif status == "pending":
        query = query.filter(Submission.submission_id.is_(None), Assignment.due_at >= now)
    rows = page_query(
        query.order_by(
            or_(Submission.submission_id.is_not(None), Assignment.due_at < now),
            Assignment.due_at,
            Assignment.assignment_id,
        ),
        response,
        skip,
        limit,
    )
    return [
        GuardianTask(
            assignment_id=task.assignment_id,
            title=task.title,
            subject_name=subject.description,
            section_code=section.code,
            due_at=task.due_at.replace(tzinfo=UTC),
            max_score=task.max_score,
            status=(
                "graded"
                if submission is not None and submission.status == "graded"
                else "submitted"
                if submission is not None
                else "overdue"
                if task.due_at < now
                else "pending"
            ),
            submitted_at=submission.submitted_at.replace(tzinfo=UTC) if submission else None,
            score=submission.score if submission and submission.status == "graded" else None,
            feedback=submission.feedback if submission and submission.status == "graded" else "",
        )
        for task, submission, section, subject in rows
    ]


@router.get("/students/{student_id}/finance", response_model=GuardianFinance)
def finance(student_id: int, db: Session = Depends(get_db), user: User = Depends(guardian)):
    link = ensure_guardian_view(db, user, student_id, "finance")
    account = get_account(db, student_id)
    due, amount = upcoming_due(account)
    return GuardianFinance(
        **summary(account).model_dump(),
        next_due_date=due,
        next_due_amount=float(amount) if amount is not None else None,
        financial_responsible=link.financial_responsible,
    )


@router.get("/students/{student_id}/statement", response_model=AccountStatement)
def statement(student_id: int, db: Session = Depends(get_db), user: User = Depends(guardian)):
    ensure_guardian_view(db, user, student_id, "finance")
    return account_statement(db, get_account(db, student_id))


@router.get("/students/{student_id}/performance", response_model=GuardianPerformance)
def performance(student_id: int, db: Session = Depends(get_db), user: User = Depends(guardian)):
    """Averages per period (oldest first) and open follow-up alerts."""
    link = ensure_guardian_view(db, user, student_id, "academic")
    attendance_allowed = link.can_view_attendance
    hidden = {"attendance"} if not link.can_view_attendance else set()
    if not link.can_view_finance:
        hidden.add("financial")
    enrollments = enrollments_of(db, student_id, None)
    names = {item.period for item in enrollments}
    starts = {
        p.name: p.start_date
        for p in db.query(AcademicPeriod).filter(AcademicPeriod.name.in_(names))
    }
    periods = []
    for name in sorted(names, key=lambda n: (starts.get(n) or date.min, n)):
        own = [item for item in enrollments if item.period == name]
        values = summarize_results(db, own)
        periods.append(
            GuardianPeriodPerformance(
                period=name,
                average_grade=values["average_grade"],
                final_grade_count=values["final_grade_count"],
                provisional_average_grade=values["provisional_average_grade"],
                provisional_grade_count=values["provisional_grade_count"],
                attendance_percentage=values["attendance_percentage"]
                if attendance_allowed
                else None,
                course_count=len(own),
            )
        )
    alerts = (
        db.query(EarlyAlert)
        .filter_by(student_id=student_id, status="open")
        .order_by(EarlyAlert.created_at.desc())
        .all()
    )
    return GuardianPerformance(
        student_id=student_id,
        periods=periods,
        alerts=[
            GuardianAlert(
                early_alert_id=alert.early_alert_id,
                category=alert.category,
                severity=alert.severity,
                reason=alert.reason,
                follow_up_date=alert.follow_up_date,
            )
            for alert in alerts
            if alert.category not in hidden
        ],
    )
