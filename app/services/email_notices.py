"""Email notices: announcements, published grades and due-date reminders (audit M6).

Recipients respect everything the interface does: active accounts, each
person's preferences, the guardian link's areas and the institution setting
for students' own finances. Every notice is queued in the caller's
transaction; duplicates are prevented by ``dedupe_key``.
"""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.auth import GUARDIAN_AREAS, account_is_active
from app.models.community_model import StudentGuardian
from app.models.finance_model import StudentAccount
from app.models.student_model import Student
from app.models.user_model import User
from app.routers.dashboard_router import display_name
from app.services import email_templates
from app.services.account_statement import account_statement
from app.services.audit_log import audit_event
from app.services.business_time import business_date
from app.services.email_service import queue_email
from app.services.email_templates import Email
from app.services.finance_workflow import cents
from app.services.institution_profile import student_sees_own_finance
from app.services.write_locks import lock_scope

# Reminders: 3 days before the due date and 1 day after if still unpaid
# (decision of 22/11/2026). Missed days catch up within these windows.
BEFORE_DAYS = 3
AFTER_DAYS = 1
CATCH_UP_DAYS = 7


def family_recipients(
    db: Session, student_id: int, area: str, preference: str, include_student: bool = True
) -> list[tuple[User, bool]]:
    """(account, is_the_student) pairs that accept this notice about the student."""
    recipients: list[tuple[User, bool]] = []
    if include_student:
        for user in db.query(User).filter(User.student_id == student_id):
            if getattr(user, preference) and account_is_active(user):
                recipients.append((user, True))
    guardians = db.query(StudentGuardian.guardian_id).filter(
        StudentGuardian.student_id == student_id,
        getattr(StudentGuardian, GUARDIAN_AREAS[area]).is_(True),
    )
    for user in db.query(User).filter(User.guardian_id.in_(guardians)):
        if getattr(user, preference) and account_is_active(user):
            recipients.append((user, False))
    return recipients


def send(db: Session, user: User, message: Email, category: str, key: str | None) -> bool:
    return (
        queue_email(
            db,
            user.email,
            message.subject,
            message.text,
            message.html,
            category=category,
            user_id=user.user_id,
            dedupe_key=key,
        )
        is not None
    )


def notify_announcement(db: Session, announcement, targets: list[User]) -> int:
    queued = 0
    for user in targets:
        if not user.email_announcements or not account_is_active(user):
            continue
        message = email_templates.announcement(
            db, display_name(db, user), announcement.title, announcement.body
        )
        key = f"announcement:{announcement.announcement_id}:user:{user.user_id}"
        queued += send(db, user, message, "announcement", key)
    return queued


def notify_grades_published(db: Session, assessment, grades) -> int:
    """One email per student and publication (and per guardian), not one per grade."""
    queued = 0
    subject = assessment.section.subject.description
    for grade in grades:
        student = grade.enrollment.student
        for user, own in family_recipients(db, student.student_id, "academic", "email_grades"):
            message = email_templates.grades_published(
                db,
                display_name(db, user),
                student.full_name,
                subject,
                assessment.name,
                grade.grade_value,
                own,
            )
            key = f"grade:{grade.grade_id}:published:user:{user.user_id}"
            queued += send(db, user, message, "grades", key)
    return queued


def reminder_phase(due: date, today: date) -> str | None:
    if due - timedelta(days=BEFORE_DAYS) <= today < due:
        return "before"
    if due + timedelta(days=AFTER_DAYS) <= today <= due + timedelta(days=CATCH_UP_DAYS):
        return "after"
    return None


def queue_due_reminders(db: Session, today: date | None = None) -> int:
    """Daily job: reminders for unpaid installments, once per phase and recipient."""
    today = today or business_date()
    lock_scope(db, "finance")
    queued = 0
    for account in db.query(StudentAccount).join(Student).filter(Student.active.is_(True)):
        statement = account_statement(db, account)
        for item in statement.obligations:
            phase = reminder_phase(item.due_date, today)
            if not phase or not cents(item.remaining):
                continue
            for user, own in family_recipients(
                db,
                account.student_id,
                "finance",
                "email_due_reminders",
                include_student=student_sees_own_finance(db, account.student_id),
            ):
                message = email_templates.due_reminder(
                    db,
                    display_name(db, user),
                    statement.student_name,
                    item.description,
                    f"RD${item.remaining:,.2f}",
                    item.due_date.strftime("%d/%m/%Y"),
                    phase,
                    own,
                )
                key = f"due:{item.type}:{item.obligation_id}:{phase}:user:{user.user_id}"
                queued += send(db, user, message, "due_reminder", key)
    audit_event(db, None, "email.due_reminders.queued", "email", f"{today}: {queued}")
    return queued
