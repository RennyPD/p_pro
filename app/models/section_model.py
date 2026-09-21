from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Section(Base):
    __tablename__ = "sections"
    __table_args__ = (CheckConstraint("start_time < end_time", name="ck_sections_time_range"),)

    section_id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str] = mapped_column(String(255))
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.teacher_id"))
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.subject_id"))
    days_of_week: Mapped[str] = mapped_column(String(255))
    start_time: Mapped[Time] = mapped_column(Time)
    end_time: Mapped[Time] = mapped_column(Time)
    capacity: Mapped[int] = mapped_column(Integer, default=30)
    room: Mapped[str] = mapped_column(String(100), default="Por asignar")
    modality: Mapped[str] = mapped_column(String(20), default="in_person")
    status: Mapped[str] = mapped_column(String(20), default="published")
    minimum_capacity: Mapped[int] = mapped_column(Integer, default=1)
    period_name: Mapped[str] = mapped_column(String(50), default="")

    subject: Mapped["Subject"] = relationship("Subject", back_populates="sections")
    teacher: Mapped["Teacher"] = relationship("Teacher", back_populates="sections")
    enrollments: Mapped[list["Enrollment"]] = relationship("Enrollment", back_populates="section")

    @property
    def teacher_name(self) -> str:
        return f"{self.teacher.first_name} {self.teacher.last_name}"

    @property
    def subject_code(self) -> str:
        return self.subject.code

    @property
    def subject_name(self) -> str:
        return self.subject.description
