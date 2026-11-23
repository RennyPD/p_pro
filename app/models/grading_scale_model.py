"""Grading scales per program (Fase 3, block D; decision 4 of 23/11/2026).

Grades are still stored from 0 to 100. A scale only decides how a value is
shown and captured (number, letter or concept), which value passes, the
weights of the completivo and extraordinario exams (schools) and the points
of each band for the academic index (universities).
"""

from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.db.tenant import TenantMixin

SCALE_KINDS = ("numeric", "letter", "conceptual")


class GradingScale(TenantMixin, Base):
    __tablename__ = "grading_scales"
    __table_args__ = (
        UniqueConstraint("institution_id", "name", name="uq_grading_scales_institution_name"),
    )

    grading_scale_id: Mapped[int] = mapped_column(primary_key=True)
    # Unique per institution once the system is multi-tenant (Fase 4).
    name: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(20), default="numeric")
    passing_value: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("70"))
    decimals: Mapped[int] = mapped_column(Integer, default=0)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    # Share of the annual average in each recovery grade; the exam is the rest.
    completivo_average_weight: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("50"))
    extraordinario_average_weight: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("30")
    )

    bands: Mapped[list["GradingScaleBand"]] = relationship(
        back_populates="scale",
        cascade="all, delete-orphan",
        order_by="GradingScaleBand.min_value",
        lazy="selectin",
    )


class GradingScaleBand(TenantMixin, Base):
    """A range [min_value, max_value) of the 0–100 scale; the top band includes 100."""

    __tablename__ = "grading_scale_bands"

    band_id: Mapped[int] = mapped_column(primary_key=True)
    grading_scale_id: Mapped[int] = mapped_column(
        ForeignKey("grading_scales.grading_scale_id"), index=True
    )
    label: Mapped[str] = mapped_column(String(40))
    description: Mapped[str | None] = mapped_column(String(120), nullable=True)
    min_value: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    max_value: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    # Value stored when a teacher picks this band (conceptual capture).
    stored_value: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    points: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)

    scale: Mapped[GradingScale] = relationship(back_populates="bands")
