from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
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
