from datetime import date

from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Student(Base):
    __tablename__ = "students"

    student_id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    enrollment_number: Mapped[str] = mapped_column(String(50), unique=True)
    telephone: Mapped[str] = mapped_column(String(20))
    address: Mapped[str] = mapped_column(String(255))
    document_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # MINERD student ID (SIGERD), printed on the official report card.
    sigerd_id: Mapped[str | None] = mapped_column(String(30), nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    nationality: Mapped[str | None] = mapped_column(String(100), nullable=True)
    admission_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    previous_school: Mapped[str | None] = mapped_column(String(255), nullable=True)
    emergency_contact_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    emergency_contact_relationship: Mapped[str | None] = mapped_column(String(60), nullable=True)
    active: Mapped[bool] = mapped_column(default=True)
    academic_hold: Mapped[bool] = mapped_column(default=False)
    financial_hold: Mapped[bool] = mapped_column(default=False)
    # "auto" when the daily finance job set the hold (and may lift it), else manual.
    financial_hold_source: Mapped[str | None] = mapped_column(String(10), nullable=True)
    career_id: Mapped[int] = mapped_column(ForeignKey("careers.career_id"))
    assigned_curriculum_version: Mapped[str | None] = mapped_column(String(30))

    career: Mapped["Career"] = relationship("Career", back_populates="students")
    enrollments: Mapped[list["Enrollment"]] = relationship("Enrollment", back_populates="student")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def career_name(self) -> str:
        return self.career.name

    @property
    def curriculum_version(self) -> str:
        return self.assigned_curriculum_version or self.career.curriculum_version
