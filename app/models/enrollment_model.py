from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.attendance_model import Attendance


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint(
            "student_id", "section_id", "period", name="uq_enrollment_student_section_period"
        ),
    )

    enrollment_id: Mapped[int] = mapped_column(primary_key=True, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.student_id"))
    section_id: Mapped[int] = mapped_column(ForeignKey("sections.section_id"))
    enrollment_date: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )
    state: Mapped[str] = mapped_column(String(50), default="enrolled")
    period: Mapped[str] = mapped_column(String(50))
    waitlist_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    passing_grade: Mapped[float | None] = mapped_column(Float, nullable=True)

    student: Mapped["Student"] = relationship("Student", back_populates="enrollments")
    section: Mapped["Section"] = relationship("Section", back_populates="enrollments")
    attendances: Mapped[list["Attendance"]] = relationship(
        "Attendance", back_populates="enrollment", cascade="all, delete-orphan"
    )
    grades: Mapped[list["Grade"]] = relationship(
        "Grade", back_populates="enrollment", cascade="all, delete-orphan"
    )

    @property
    def student_name(self) -> str:
        return f"{self.student.first_name} {self.student.last_name}"

    @property
    def section_code(self) -> str:
        return self.section.code

    @property
    def subject_name(self) -> str:
        return self.section.subject.description


class CourseSelectionCart(Base):
    __tablename__ = "course_selection_cart"
    __table_args__ = (
        UniqueConstraint(
            "student_id", "section_id", "period", name="uq_cart_student_section_period"
        ),
    )

    cart_item_id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.student_id"))
    section_id: Mapped[int] = mapped_column(ForeignKey("sections.section_id"))
    period: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )

    section: Mapped["Section"] = relationship("Section")
