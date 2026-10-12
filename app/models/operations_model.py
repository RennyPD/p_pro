from datetime import UTC, date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


def now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class CalendarEvent(Base):
    __tablename__ = "calendar_events"
    calendar_event_id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(Text, default="")
    event_type: Mapped[str] = mapped_column(String(30), default="activity")
    audience: Mapped[str] = mapped_column(String(20), default="all")
    section_id: Mapped[int | None] = mapped_column(ForeignKey("sections.section_id"), nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime)
    ends_at: Mapped[datetime] = mapped_column(DateTime)
    no_school: Mapped[bool] = mapped_column(default=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.user_id"))


class LessonPlan(Base):
    __tablename__ = "lesson_plans"
    lesson_plan_id: Mapped[int] = mapped_column(primary_key=True)
    section_id: Mapped[int] = mapped_column(ForeignKey("sections.section_id"))
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.teacher_id"))
    scheduled_date: Mapped[date] = mapped_column(Date)
    title: Mapped[str] = mapped_column(String(150))
    content: Mapped[str] = mapped_column(Text)
    competencies: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="planned")


class Assignment(Base):
    __tablename__ = "assignments"
    __table_args__ = (
        Index(
            "uq_assignment_assessment",
            "assessment_id",
            unique=True,
            sqlite_where=text("assessment_id IS NOT NULL"),
            postgresql_where=text("assessment_id IS NOT NULL"),
        ),
    )
    assignment_id: Mapped[int] = mapped_column(primary_key=True)
    section_id: Mapped[int] = mapped_column(ForeignKey("sections.section_id"))
    title: Mapped[str] = mapped_column(String(150))
    instructions: Mapped[str] = mapped_column(Text)
    due_at: Mapped[datetime] = mapped_column(DateTime)
    max_score: Mapped[float] = mapped_column(Float, default=100)
    assessment_id: Mapped[int | None] = mapped_column(
        ForeignKey("assessments.assessment_id"), nullable=True
    )
    created_by: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    published: Mapped[bool] = mapped_column(default=True)
    lifecycle: Mapped[str] = mapped_column(String(20), default="open", server_default="open")
    allow_late: Mapped[bool] = mapped_column(default=False, server_default="0")
    allow_resubmit: Mapped[bool] = mapped_column(default=True, server_default="1")


class Submission(Base):
    __tablename__ = "submissions"
    __table_args__ = (
        UniqueConstraint("assignment_id", "student_id", name="uq_assignment_student"),
    )
    submission_id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.assignment_id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("students.student_id"))
    content: Mapped[str] = mapped_column(Text)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    status: Mapped[str] = mapped_column(String(20), default="submitted")
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    feedback: Mapped[str] = mapped_column(Text, default="")


class SubmissionRevision(Base):
    __tablename__ = "submission_revisions"
    revision_id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.submission_id"))
    content: Mapped[str] = mapped_column(Text)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class EarlyAlert(Base):
    __tablename__ = "early_alerts"
    early_alert_id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.student_id"))
    category: Mapped[str] = mapped_column(String(30))
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"), nullable=True)
    assigned_to: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"), nullable=True)
    follow_up_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    resolution_notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AlertIntervention(Base):
    __tablename__ = "alert_interventions"
    alert_intervention_id: Mapped[int] = mapped_column(primary_key=True)
    early_alert_id: Mapped[int] = mapped_column(ForeignKey("early_alerts.early_alert_id"))
    action_type: Mapped[str] = mapped_column(String(30))
    notes: Mapped[str] = mapped_column(Text)
    performed_by: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class AdmissionApplication(Base):
    __tablename__ = "admission_applications"
    admission_application_id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    telephone: Mapped[str] = mapped_column(String(30))
    career_id: Mapped[int] = mapped_column(ForeignKey("careers.career_id"))
    status: Mapped[str] = mapped_column(String(20), default="submitted")
    checklist: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"
    approval_request_id: Mapped[int] = mapped_column(primary_key=True)
    request_type: Mapped[str] = mapped_column(String(40))
    resource_type: Mapped[str] = mapped_column(String(40))
    resource_id: Mapped[int] = mapped_column()
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"), nullable=True)
    resolution_notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class StudentDocument(Base):
    __tablename__ = "student_documents"
    student_document_id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.student_id"))
    document_type: Mapped[str] = mapped_column(String(50))
    filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(100))
    content: Mapped[bytes] = mapped_column(LargeBinary)
    expires_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=now)
