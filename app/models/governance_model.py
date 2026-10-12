from datetime import UTC, date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class CourseEquivalence(Base):
    __tablename__ = "course_equivalences"
    __table_args__ = (
        UniqueConstraint(
            "career_id",
            "source_subject_id",
            "target_subject_id",
            "curriculum_version",
            name="uq_course_equivalence",
        ),
    )
    course_equivalence_id: Mapped[int] = mapped_column(primary_key=True)
    career_id: Mapped[int] = mapped_column(ForeignKey("careers.career_id"))
    source_subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.subject_id"))
    target_subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.subject_id"))
    curriculum_version: Mapped[str] = mapped_column(String(30), default="current")
    notes: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"), nullable=True)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class StudentCareerHistory(Base):
    __tablename__ = "student_career_history"
    student_career_history_id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.student_id"))
    previous_career_id: Mapped[int] = mapped_column(ForeignKey("careers.career_id"))
    new_career_id: Mapped[int] = mapped_column(ForeignKey("careers.career_id"))
    effective_date: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(Text)
    changed_by: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )
