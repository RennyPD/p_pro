from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Grade(Base):
    __tablename__ = "grades"
    __table_args__ = (
        CheckConstraint("grade_value >= 0 AND grade_value <= 100", name="ck_grades_value_range"),
    )

    grade_id: Mapped[int] = mapped_column(primary_key=True, index=True)
    enrollment_id: Mapped[int] = mapped_column(ForeignKey("enrollments.enrollment_id"))
    assessment_id: Mapped[int | None] = mapped_column(
        ForeignKey("assessments.assessment_id"), nullable=True
    )
    grade_value: Mapped[float] = mapped_column(Float)
    grade_type: Mapped[str] = mapped_column(String(50))
    date_recorded: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="published")
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )

    enrollment: Mapped["Enrollment"] = relationship("Enrollment", back_populates="grades")
    assessment: Mapped["Assessment | None"] = relationship("Assessment", back_populates="grades")


class GradeChange(Base):
    __tablename__ = "grade_changes"
    grade_change_id: Mapped[int] = mapped_column(primary_key=True)
    grade_id: Mapped[int] = mapped_column(ForeignKey("grades.grade_id"))
    previous_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    new_value: Mapped[float] = mapped_column(Float)
    changed_by: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    reason: Mapped[str] = mapped_column(String(250), default="Registro de calificación")
    changed_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )
