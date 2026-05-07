from sqlalchemy import ForeignKey, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base

class Section(Base):
    __tablename__ = "sections"

    section_id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str] = mapped_column(String(255))
    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("teachers.teacher_id")
    )
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.subject_id")
    )
    days_of_week: Mapped[str] = mapped_column(String(255))
    start_time: Mapped[Time] = mapped_column(Time)
    end_time: Mapped[Time] = mapped_column(Time)
    
    subject: Mapped["Subject"] = relationship("Subject", back_populates="sections")
    teacher: Mapped["Teacher"] = relationship("Teacher", back_populates="sections")
    enrollments: Mapped[list["Enrollment"]] = relationship("Enrollment", back_populates="section")
