from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Career(Base):
    __tablename__ = "careers"

    career_id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str] = mapped_column(String(255))
    code: Mapped[str] = mapped_column(String(30), unique=True)
    academic_level: Mapped[str] = mapped_column(String(30), default="undergraduate")
    degree_title: Mapped[str] = mapped_column(String(150), default="")
    term_type: Mapped[str] = mapped_column(String(20), default="semester")
    duration_terms: Mapped[int] = mapped_column(Integer, default=8)
    required_credits: Mapped[int] = mapped_column(Integer, default=120)
    curriculum_version: Mapped[str] = mapped_column(String(30), default="current")

    students: Mapped[list["Student"]] = relationship("Student", back_populates="career")
