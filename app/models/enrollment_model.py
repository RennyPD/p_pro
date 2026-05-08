from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base
from app.models.attendance_model import Attendance

class Enrollment(Base):
    __tablename__ = "enrollments"

    enrollment_id: Mapped[int] = mapped_column(primary_key=True, index=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.student_id")
    )
    section_id: Mapped[int] = mapped_column(
        ForeignKey("sections.section_id")
    )
    enrollment_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    state: Mapped[str] = mapped_column(String(50), default="enrolled")
    period: Mapped[str] = mapped_column(String(50))

    student: Mapped["Student"] = relationship("Student", back_populates="enrollments")
    section: Mapped["Section"] = relationship("Section", back_populates="enrollments")
    attendances: Mapped[list["Attendance"]] = relationship("Attendance", back_populates="enrollment")
    grades: Mapped[list["Grade"]] = relationship("Grade", back_populates="enrollment")