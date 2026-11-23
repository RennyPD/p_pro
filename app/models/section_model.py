from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.period_link import period_by_name


class Section(Base):
    __tablename__ = "sections"
    __table_args__ = (CheckConstraint("start_time < end_time", name="ck_sections_time_range"),)

    section_id: Mapped[int] = mapped_column(primary_key=True)
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
    # Linked by id since migration 0054; period_name is the period's name (B5).
    period_id: Mapped[int | None] = mapped_column(
        ForeignKey("academic_periods.period_id"), nullable=True, index=True
    )
    academic_period: Mapped["AcademicPeriod | None"] = relationship(lazy="selectin")
    period_name = period_by_name("period_name")

    subject: Mapped["Subject"] = relationship("Subject", back_populates="sections")
    teacher: Mapped["Teacher"] = relationship("Teacher", back_populates="sections")
    enrollments: Mapped[list["Enrollment"]] = relationship("Enrollment", back_populates="section")
    meetings: Mapped[list["SectionMeeting"]] = relationship(
        "SectionMeeting", back_populates="section"
    )

    @property
    def teacher_name(self) -> str:
        return f"{self.teacher.first_name} {self.teacher.last_name}"

    @property
    def subject_code(self) -> str:
        return self.subject.code

    @property
    def subject_name(self) -> str:
        return self.subject.description
