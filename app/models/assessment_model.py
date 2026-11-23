from datetime import date

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.db.tenant import TenantMixin


class Assessment(TenantMixin, Base):
    __tablename__ = "assessments"
    __table_args__ = (
        UniqueConstraint("section_id", "name", name="uq_assessment_section_name"),
        Index("idx_assessments_section", "section_id"),
    )

    assessment_id: Mapped[int] = mapped_column(primary_key=True)
    section_id: Mapped[int] = mapped_column(ForeignKey("sections.section_id"))
    name: Mapped[str] = mapped_column(String(100))
    weight: Mapped[float] = mapped_column(Float)

    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    closed: Mapped[bool] = mapped_column(Boolean, default=False)
    # MINERD competency group this assessment grades (Fase 3 F2); None otherwise.
    competency_group_id: Mapped[int | None] = mapped_column(
        ForeignKey("competency_groups.competency_group_id"), nullable=True
    )

    section: Mapped["Section"] = relationship("Section")
    grades: Mapped[list["Grade"]] = relationship("Grade", back_populates="assessment")


class CompetencyGroup(TenantMixin, Base):
    """A group of MINERD fundamental competencies graded per subject and period (Fase 3 F2).

    The secondary report card grades each subject on four groups; the period
    result (PC) is their average. One row per group, per institution later.
    """

    __tablename__ = "competency_groups"
    __table_args__ = (
        UniqueConstraint(
            "institution_id", "position", name="uq_competency_groups_institution_position"
        ),
    )

    competency_group_id: Mapped[int] = mapped_column(primary_key=True)
    position: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(150))
    short_name: Mapped[str] = mapped_column(String(40))


class AssessmentTemplate(TenantMixin, Base):
    __tablename__ = "assessment_templates"
    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_assessment_template_owner_name"),
    )

    assessment_template_id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    name: Mapped[str] = mapped_column(String(100))
    weight: Mapped[float] = mapped_column(Float)
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.subject_id"), nullable=True)
    components: Mapped[list | None] = mapped_column(JSON, nullable=True)
