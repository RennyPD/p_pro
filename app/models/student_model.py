from sqlalchemy import String, ForeignKey
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
    active: Mapped[bool] = mapped_column(default=True)
    career_id: Mapped[int] = mapped_column(ForeignKey("careers.career_id"))

    career: Mapped["Career"] = relationship("Career", back_populates="students")
    enrollments: Mapped[list["Enrollment"]] = relationship(
    "Enrollment",
    back_populates="student"
    )