"""Detail a guardian sees of each linked student (audit A1, M8).

Every route checks that the student is linked to the guardian account and that
the link allows the area (``ensure_guardian_view``). By default a guardian sees
everything; the institution restricts single links from the student's record.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.auth import ensure_guardian_view, require_personal
from app.db.database import settings
from app.db.Session import get_db
from app.models.assessment_model import Assessment
from app.models.community_model import StudentGuardian
from app.models.configuration_model import AcademicPeriod
from app.models.enrollment_model import Enrollment
from app.models.finance_model import TransferBatch, TransferRequest
from app.models.operations_model import Assignment, EarlyAlert, Submission
from app.models.section_model import Section
from app.models.student_model import Student
from app.models.subject_model import Subject
from app.models.user_model import User
from app.pagination import page_query
from app.schemas.academic_schema import AttendanceCourseSummary, RosterAttendanceItem
from app.schemas.finance_schema import AccountStatement
from app.schemas.guardian_schema import (
    FamilyConcept,
    FamilyConceptShare,
    FamilyFinance,
    FamilyStudentBalance,
    FamilySuggestion,
    FamilyTransferCreate,
    FamilyTransferOut,
    FamilyTransferShare,
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
from app.services import storage
from app.services.academic_grading import academic_result
from app.services.academic_metrics import summarize_results
from app.services.account_statement import account_statement
from app.services.finance_workflow import (
    cents,
    decode_proof,
    ensure_new_reference,
    event,
    get_account,
    lock_finance,
    money,
    summary,
    upcoming_due,
    writable_account,
)
from app.services.grading_scales import brief, label, scale_for_student

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
    scale = scale_for_student(db, db.get(Student, student_id))
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
                grade_label=label(scale, grade.grade_value) if grade else None,
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
                    grade_label=label(scale, grade.grade_value),
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
                result_label=label(scale, result.value),
                result_status=result.status,
                final=result.final,
                completed_weight=result.completed_weight,
                configured_weight=result.configured_weight,
                assessments=assessments,
            )
        )
    return GuardianGrades(
        student_id=student_id, period=period, courses=courses, grading_scale=brief(scale)
    )


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


# Pagos de la familia: total, reparto sugerido y una transferencia para varios hijos.


def finance_links(db: Session, user: User) -> list[StudentGuardian]:
    """Links of the guardian that allow finances, in a stable order."""
    return (
        db.query(StudentGuardian)
        .filter(
            StudentGuardian.guardian_id == user.guardian_id,
            StudentGuardian.can_view_finance.is_(True),
        )
        .order_by(StudentGuardian.student_id)
        .all()
    )


def family_statements(db: Session, user: User):
    return [
        (link, account_statement(db, get_account(db, link.student_id)))
        for link in finance_links(db, user)
    ]


@router.get("/finance", response_model=FamilyFinance)
def family_finance(db: Session = Depends(get_db), user: User = Depends(guardian)):
    """Family total with the breakdown per child and per concept."""
    statements = family_statements(db, user)
    concepts: dict[str, dict[int, int]] = {}
    for _, statement in statements:
        for concept in statement.concepts:
            if concept.remaining:
                shares = concepts.setdefault(concept.concept, {})
                shares[statement.student_id] = shares.get(statement.student_id, 0) + cents(
                    concept.remaining
                )
    dues = [s.next_due_date for _, s in statements if s.next_due_date]
    return FamilyFinance(
        total_balance=money(sum(cents(s.balance) for _, s in statements)),
        total_overdue=money(sum(cents(s.overdue_balance) for _, s in statements)),
        next_due_date=min(dues) if dues else None,
        students=[
            FamilyStudentBalance(
                student_id=s.student_id,
                student_name=s.student_name,
                enrollment_number=s.enrollment_number,
                balance=s.balance,
                overdue_balance=s.overdue_balance,
                next_due_date=s.next_due_date,
                next_due_amount=s.next_due_amount,
                financial_responsible=link.financial_responsible,
            )
            for link, s in statements
        ],
        concepts=[
            FamilyConcept(
                concept=name,
                remaining=money(sum(shares.values())),
                students=[
                    FamilyConceptShare(student_id=student_id, remaining=money(amount))
                    for student_id, amount in sorted(shares.items())
                ],
            )
            for name, shares in sorted(concepts.items())
        ],
    )


def suggest_allocation(statements, amount_cents: int) -> list[FamilySuggestion]:
    """Pay what is due first, whichever child it belongs to (decision of 22/11/2026)."""
    pending = sorted(
        (o.due_date, s.student_id, o.type, o.obligation_id, cents(o.remaining))
        for _, s in statements
        for o in s.obligations
        if o.remaining
    )
    shares: dict[int, int] = {}
    for _, student_id, _, _, remaining in pending:
        if amount_cents <= 0:
            break
        part = min(remaining, amount_cents)
        shares[student_id] = shares.get(student_id, 0) + part
        amount_cents -= part
    return [
        FamilySuggestion(student_id=student_id, amount=money(part))
        for student_id, part in sorted(shares.items())
    ]


@router.get("/finance/allocation", response_model=list[FamilySuggestion])
def family_allocation(
    amount: Decimal = Query(gt=0, le=Decimal("999999999.99"), decimal_places=2),
    db: Session = Depends(get_db),
    user: User = Depends(guardian),
):
    statements = family_statements(db, user)
    total = sum(cents(s.balance) for _, s in statements)
    if cents(amount) > total:
        raise HTTPException(422, "El monto supera el balance pendiente de la familia")
    return suggest_allocation(statements, cents(amount))


def batch_out(db: Session, batch: TransferBatch) -> FamilyTransferOut:
    names = {
        s.student_id: s.full_name
        for s in db.query(Student).filter(
            Student.student_id.in_([share.student_id for share in batch.requests])
        )
    }
    return FamilyTransferOut(
        transfer_batch_id=batch.transfer_batch_id,
        reference=batch.reference,
        bank=batch.bank,
        total=money(batch.total_cents),
        status=batch.status,
        submitted_at=batch.submitted_at.replace(tzinfo=UTC),
        review_reason=batch.review_reason,
        shares=[
            FamilyTransferShare(
                transfer_request_id=share.transfer_request_id,
                student_id=share.student_id,
                student_name=names.get(share.student_id, ""),
                amount=money(share.amount_cents),
                status=share.status,
            )
            for share in batch.requests
        ],
    )


@router.post("/transfers", response_model=FamilyTransferOut)
def submit_family_transfer(
    data: FamilyTransferCreate, db: Session = Depends(get_db), user: User = Depends(guardian)
):
    """One bank transfer split among several linked children."""
    if not settings.finance_transfer_instructions.strip():
        raise HTTPException(409, "La institución aún no configuró sus instrucciones bancarias")
    lock_finance(db)
    students = [item.student_id for item in data.allocations]
    if len(students) != len(set(students)):
        raise HTTPException(422, "Cada estudiante aparece una sola vez en el reparto")
    allowed = {link.student_id for link in finance_links(db, user)}
    if not set(students) <= allowed:
        raise HTTPException(403, "Solo puedes repartir pagos entre tus estudiantes vinculados")
    ensure_new_reference(db, data.reference)
    proof, mime = decode_proof(data.proof_base64)
    for item in data.allocations:
        account = writable_account(db, item.student_id)
        if cents(item.amount) > cents(summary(account).balance):
            raise HTTPException(
                422, "El reparto supera el balance pendiente de uno de los estudiantes"
            )
    stored = storage.store(db, "transfers", proof, mime)
    batch = TransferBatch(
        reference=data.reference,
        bank=data.bank,
        note=data.note,
        total_cents=sum(cents(item.amount) for item in data.allocations),
        proof_key=stored.key,
        proof_size=stored.size,
        proof_sha256=stored.sha256,
        proof_type=mime,
        status="pending",
        submitted_by=user.user_id,
    )
    db.add(batch)
    db.flush()
    count = len(data.allocations)
    for index, item in enumerate(data.allocations, start=1):
        share = TransferRequest(
            student_id=item.student_id,
            amount_cents=cents(item.amount),
            # Each payment needs its own reference; the bank's stays on the batch.
            reference=f"{data.reference[:88]} ({index}/{count})",
            bank=data.bank,
            note=data.note,
            proof=None,
            proof_type=mime,
            status="pending",
            submitted_by=user.user_id,
            batch_id=batch.transfer_batch_id,
        )
        db.add(share)
        db.flush()
        event(
            db,
            user,
            item.student_id,
            "transfer.submitted",
            {
                "request_id": share.transfer_request_id,
                "batch_id": batch.transfer_batch_id,
                "reference": data.reference,
                "amount_cents": share.amount_cents,
            },
        )
    db.commit()
    db.refresh(batch)
    return batch_out(db, batch)


@router.get("/transfers", response_model=list[FamilyTransferOut])
def family_transfers(db: Session = Depends(get_db), user: User = Depends(guardian)):
    """Family transfers that include at least one of the guardian's linked students."""
    students = [link.student_id for link in finance_links(db, user)]
    batches = (
        db.query(TransferBatch)
        .filter(
            TransferBatch.transfer_batch_id.in_(
                db.query(TransferRequest.batch_id).filter(TransferRequest.student_id.in_(students))
            )
        )
        .order_by(TransferBatch.submitted_at.desc())
        .limit(50)
        .all()
    )
    return [batch_out(db, batch) for batch in batches]
