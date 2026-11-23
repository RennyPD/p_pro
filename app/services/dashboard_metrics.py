"""Actionable figures for the home page (Fase 2 redesign).

Each figure answers "what should I do now" for the account: classes still
without attendance today, grades to publish, submissions to review, money to
collect. Every query is limited to the account's scope.
"""

from datetime import UTC, datetime, time

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.enums.dayEnum import DayEnum
from app.models.attendance_model import Attendance
from app.models.enrollment_model import Enrollment
from app.models.finance_model import Payment, StudentAccount, TransferRequest
from app.models.grade_model import Grade
from app.models.operations_model import Assignment, Submission
from app.models.section_model import Section
from app.schemas.dashboard_schema import DashboardMetric
from app.services.business_time import business_date, business_day_utc_range
from app.services.effective_schedule import effective_blocks
from app.services.finance_workflow import cents, get_account, money, summary
from app.services.institution_profile import student_sees_own_finance

WEEKDAYS = [day.value for day in DayEnum]
ACTIVE_STATES = ("enrolled", "completed", "failed")


def sections_without_attendance_today(db: Session, teacher_id: int) -> int:
    """Sections that meet today and have no attendance recorded for today yet."""
    today = business_date()
    name = WEEKDAYS[today.weekday()]
    midnight = datetime.combine(today, time.min)
    pending = 0
    sections = (
        db.query(Section)
        .options(selectinload(Section.meetings))
        .filter(Section.teacher_id == teacher_id, Section.status.in_(("published", "active")))
    )
    for section in sections:
        if not any(block.day_of_week == name for block in effective_blocks(section)):
            continue
        taken = (
            db.query(Attendance.attendance_id)
            .join(Enrollment, Enrollment.enrollment_id == Attendance.enrollment_id)
            .filter(Enrollment.section_id == section.section_id, Attendance.date == midnight)
            .first()
        )
        enrolled = (
            db.query(Enrollment.enrollment_id)
            .filter_by(section_id=section.section_id, state="enrolled")
            .first()
        )
        if enrolled and not taken:
            pending += 1
    return pending


def teacher_metrics(db: Session, teacher_id: int) -> list[DashboardMetric]:
    in_my_sections = Section.teacher_id == teacher_id
    drafts = (
        db.query(func.count(Grade.grade_id))
        .join(Enrollment, Enrollment.enrollment_id == Grade.enrollment_id)
        .join(Section, Section.section_id == Enrollment.section_id)
        .filter(in_my_sections, Grade.status == "draft", Enrollment.state.in_(ACTIVE_STATES))
        .scalar()
        or 0
    )
    to_review = (
        db.query(func.count(Submission.submission_id))
        .join(Assignment, Assignment.assignment_id == Submission.assignment_id)
        .join(Section, Section.section_id == Assignment.section_id)
        .filter(in_my_sections, Submission.status != "graded")
        .scalar()
        or 0
    )
    students = (
        db.query(func.count(func.distinct(Enrollment.student_id)))
        .join(Section, Section.section_id == Enrollment.section_id)
        .filter(in_my_sections, Enrollment.state == "enrolled")
        .scalar()
        or 0
    )
    attendance = sections_without_attendance_today(db, teacher_id)
    return [
        DashboardMetric(
            key="attendance_today",
            label="Pase de lista pendiente",
            value=attendance,
            note="Secciones de hoy sin asistencia" if attendance else "Al día",
            tone="warning" if attendance else "success",
            link="/attendances" if attendance else None,
        ),
        DashboardMetric(
            key="drafts",
            label="Notas por publicar",
            value=drafts,
            note="En borrador" if drafts else "Todo publicado",
            tone="warning" if drafts else "success",
            link="/assessments" if drafts else None,
        ),
        DashboardMetric(
            key="submissions",
            label="Entregas por revisar",
            value=to_review,
            note="Sin calificar" if to_review else "Al día",
            tone="info" if to_review else "success",
            link="/operations" if to_review else None,
        ),
        DashboardMetric(
            key="students",
            label="Mis estudiantes",
            value=students,
            note="Inscritos en mis secciones",
            link="/students",
        ),
    ]


def finance_metrics(db: Session) -> list[DashboardMetric]:
    """Only for accounts with finance.view (the caller checks)."""
    today = business_date()
    start, _ = business_day_utc_range(today.replace(day=1))
    collected = (
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(Payment.status == "posted", Payment.paid_at >= start)
        .scalar()
    )
    overdue = 0
    accounts = db.query(StudentAccount).options(
        selectinload(StudentAccount.charges),
        selectinload(StudentAccount.payments),
        selectinload(StudentAccount.adjustments),
        selectinload(StudentAccount.student),
    )
    for account in accounts:
        overdue += cents(summary(account).overdue_balance)
    pending = (
        db.query(TransferRequest)
        .filter(TransferRequest.status == "pending")
        .with_entities(TransferRequest.batch_id, TransferRequest.transfer_request_id)
        .all()
    )
    reports = len({f"b{b}" if b else f"t{t}" for b, t in pending})
    return [
        DashboardMetric(
            key="collected_month",
            label="Cobrado este mes",
            value=float(collected or 0),
            note=today.strftime("%m/%Y"),
            tone="success",
            format="money",
            link="/finance",
        ),
        DashboardMetric(
            key="overdue",
            label="Saldo vencido",
            value=float(money(overdue)),
            note="De todas las cuentas",
            tone="danger" if overdue else "success",
            format="money",
            link="/finance",
        ),
        DashboardMetric(
            key="pending_transfers",
            label="Transferencias por revisar",
            value=reports,
            note="Reportadas por familias" if reports else "Bandeja vacía",
            tone="warning" if reports else "success",
            link="/finance" if reports else None,
        ),
    ]


def student_extra_metrics(db: Session, student_id: int) -> list[DashboardMetric]:
    now = datetime.now(UTC).replace(tzinfo=None)
    sections = db.query(Enrollment.section_id).filter(
        Enrollment.student_id == student_id, Enrollment.state == "enrolled"
    )
    submitted = db.query(Submission.assignment_id).filter(Submission.student_id == student_id)
    pending_tasks = (
        db.query(func.count(Assignment.assignment_id))
        .filter(
            Assignment.section_id.in_(sections),
            Assignment.published.is_(True),
            Assignment.due_at >= now,
            Assignment.assignment_id.not_in(submitted),
        )
        .scalar()
        or 0
    )
    metrics = [
        DashboardMetric(
            key="pending_tasks",
            label="Tareas por entregar",
            value=pending_tasks,
            note="Antes de su fecha límite" if pending_tasks else "Al día",
            tone="warning" if pending_tasks else "success",
            link="/operations" if pending_tasks else None,
        )
    ]
    if student_sees_own_finance(db, student_id):
        totals = summary(get_account(db, student_id))
        metrics.append(
            DashboardMetric(
                key="balance",
                label="Mi balance",
                value=float(totals.balance),
                note="Con monto vencido" if totals.overdue_balance > 0 else "Al día",
                tone="danger" if totals.overdue_balance > 0 else "default",
                format="money",
                link="/my-finance",
            )
        )
    return metrics
