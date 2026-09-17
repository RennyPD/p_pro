from sqlalchemy import Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class CurriculumCourse(Base):
    __tablename__ = "curriculum_courses"
    __table_args__ = (
        UniqueConstraint("career_id", "subject_id", name="uq_curriculum_career_subject"),
    )

    curriculum_course_id: Mapped[int] = mapped_column(primary_key=True)
    career_id: Mapped[int] = mapped_column(ForeignKey("careers.career_id"))
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.subject_id"))
    term_number: Mapped[int] = mapped_column(Integer)
    credits: Mapped[float] = mapped_column(Float, default=3)
    prerequisite_subject_id: Mapped[int | None] = mapped_column(
        ForeignKey("subjects.subject_id"), nullable=True
    )

    career: Mapped["Career"] = relationship("Career")
    subject: Mapped["Subject"] = relationship("Subject", foreign_keys=[subject_id])
    prerequisite: Mapped["Subject | None"] = relationship(
        "Subject", foreign_keys=[prerequisite_subject_id]
    )
