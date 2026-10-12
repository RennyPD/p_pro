from datetime import date

from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Student(Base):
    __tablename__ = "students"

    student_id: Mapped[int] = mapped_column(primary_key=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    enrollment_number: Mapped[str] = mapped_column(String(50), unique=True)
    telephone: Mapped[str] = mapped_column(String(20))
    address: Mapped[str] = mapped_column(String(255))
    document_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
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
    career_id: Mapped[int] = mapped_column(ForeignKey("careers.career_id"))

    career: Mapped["Career"] = relationship("Career", back_populates="students")
    enrollments: Mapped[list["Enrollment"]] = relationship("Enrollment", back_populates="student")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def career_name(self) -> str:
        return self.career.name
