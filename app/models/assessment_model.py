from datetime import date

from sqlalchemy import Boolean, Date, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Assessment(Base):
    __tablename__ = "assessments"
    __table_args__ = (UniqueConstraint("section_id", "name", name="uq_assessment_section_name"),)

    assessment_id: Mapped[int] = mapped_column(primary_key=True)
    section_id: Mapped[int] = mapped_column(ForeignKey("sections.section_id"))
    name: Mapped[str] = mapped_column(String(100))
    weight: Mapped[float] = mapped_column(Float)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    closed: Mapped[bool] = mapped_column(Boolean, default=False)

    section: Mapped["Section"] = relationship("Section")
    grades: Mapped[list["Grade"]] = relationship("Grade", back_populates="assessment")
