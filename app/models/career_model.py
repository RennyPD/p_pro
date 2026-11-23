from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.db.tenant import TenantMixin


class Career(TenantMixin, Base):
    __tablename__ = "careers"
    __table_args__ = (
        UniqueConstraint("institution_id", "name", name="uq_careers_institution_name"),
        UniqueConstraint("institution_id", "code", name="uq_careers_institution_code"),
    )

    career_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(255))
    code: Mapped[str] = mapped_column(String(30))
    academic_level: Mapped[str] = mapped_column(String(30), default="undergraduate")
    degree_title: Mapped[str] = mapped_column(String(150), default="")
    term_type: Mapped[str] = mapped_column(String(20), default="semester")
    duration_terms: Mapped[int] = mapped_column(Integer, default=8)
    required_credits: Mapped[int] = mapped_column(Integer, default=120)
    curriculum_version: Mapped[str] = mapped_column(String(30), default="current")

    status: Mapped[str] = mapped_column(String(20), default="active")
    modality: Mapped[str] = mapped_column(String(20), default="in_person")
    faculty: Mapped[str | None] = mapped_column(String(150), nullable=True)
    department: Mapped[str | None] = mapped_column(String(150), nullable=True)
    coordinator_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    campus: Mapped[str | None] = mapped_column(String(150), nullable=True)
    authorization_reference: Mapped[str | None] = mapped_column(String(150), nullable=True)
    admission_profile: Mapped[str | None] = mapped_column(Text, nullable=True)
    graduate_profile: Mapped[str | None] = mapped_column(Text, nullable=True)
    professional_fields: Mapped[str | None] = mapped_column(Text, nullable=True)
    admission_requirements: Mapped[str | None] = mapped_column(Text, nullable=True)
    graduation_requirements: Mapped[str | None] = mapped_column(Text, nullable=True)

    # None: the institution's default scale (Fase 3 D).
    grading_scale_id: Mapped[int | None] = mapped_column(
        ForeignKey("grading_scales.grading_scale_id"), nullable=True, index=True
    )
    grading_scale: Mapped["GradingScale | None"] = relationship(lazy="selectin")
    # general | minerd_secondary (Fase 3 F2): the official secondary report card,
    # graded by competency groups.
    report_card_format: Mapped[str] = mapped_column(
        String(30), default="general", server_default="general"
    )

    students: Mapped[list["Student"]] = relationship("Student", back_populates="career")
