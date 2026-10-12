from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Attendance(Base):
    __tablename__ = "attendances"

    attendance_id: Mapped[int] = mapped_column(primary_key=True, index=True)
    enrollment_id: Mapped[int] = mapped_column(ForeignKey("enrollments.enrollment_id"))
    date: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )
    present: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="absent")
    note: Mapped[str] = mapped_column(String(300), default="")
    excuse_reference: Mapped[str] = mapped_column(String(300), default="")
    __table_args__ = (
        Index("uq_attendance_enrollment_day", "enrollment_id", func.date(date), unique=True),
    )

    enrollment: Mapped["Enrollment"] = relationship("Enrollment", back_populates="attendances")

    @property
    def student_name(self) -> str:
        return f"{self.enrollment.student.first_name} {self.enrollment.student.last_name}"

    @property
    def section_code(self) -> str:
        return self.enrollment.section.code

    @property
    def subject_name(self) -> str:
        return self.enrollment.section.subject.description


class AttendanceChange(Base):
    """Snapshots survive physical deletion without cascading away the audit."""

    __tablename__ = "attendance_changes"
    change_id: Mapped[int] = mapped_column(primary_key=True)
    attendance_id: Mapped[int] = mapped_column(index=True)
    enrollment_id: Mapped[int] = mapped_column(index=True)
    changed_by: Mapped[int] = mapped_column()
    changed_by_name: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(String(250))
    previous: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    current: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )
