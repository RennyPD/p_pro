from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, Text, func, select, true
from sqlalchemy.orm import Mapped, column_property, mapped_column, relationship

from app.db.database import Base
from app.models.school_year_link import school_year_by_name


class SchoolYear(Base):
    """A school or academic year (e.g. "2026-2027") that groups its periods (Fase 3 B)."""

    __tablename__ = "school_years"

    school_year_id: Mapped[int] = mapped_column(primary_key=True)
    # Unique per institution once the system is multi-tenant (Fase 4).
    name: Mapped[str] = mapped_column(String(20), unique=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    # quarters (4, MINERD) | trimesters | bimesters | quadrimesters | semesters | annual
    period_scheme: Mapped[str] = mapped_column(
        String(20), default="semesters", server_default="semesters"
    )
    periods: Mapped[list["AcademicPeriod"]] = relationship(
        back_populates="school_year", order_by="AcademicPeriod.start_date"
    )


class AcademicPeriod(Base):
    __tablename__ = "academic_periods"

    period_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="planning")
    registration_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    registration_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    withdrawal_deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    grading_deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_type: Mapped[str] = mapped_column(String(20), default="semester")
    sequence: Mapped[int] = mapped_column(Integer, default=1)
    # Linked by id since migration 0056; academic_year is the year's name.
    school_year_id: Mapped[int | None] = mapped_column(
        ForeignKey("school_years.school_year_id"), nullable=True, index=True
    )
    school_year: Mapped[SchoolYear | None] = relationship(back_populates="periods", lazy="selectin")
    academic_year = school_year_by_name()
    closure_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)


class InstitutionSettings(Base):
    __tablename__ = "institution_settings"

    settings_id: Mapped[int] = mapped_column(primary_key=True, default=1)
    institution_name: Mapped[str] = mapped_column(String(150), default="Nexo Académico")
    enrollment_prefix: Mapped[str] = mapped_column(String(20), default="EST")
    enrollment_digits: Mapped[int] = mapped_column(Integer, default=4)
    next_enrollment_number: Mapped[int] = mapped_column(Integer, default=1)
    passing_grade: Mapped[float] = mapped_column(default=70.0)
    max_credits_per_period: Mapped[int] = mapped_column(Integer, default=24)
    # Whether students see their own account in their portal (product decision
    # 21/11/2026: configurable per institution; usually no in schools, yes in
    # universities). Staff and linked guardians are not affected.
    # university | school | both (Fase 3). Existing installations are universities.
    institution_type: Mapped[str] = mapped_column(
        String(20), default="university", server_default="university"
    )
    students_view_finance: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=true()
    )
    # MINERD identification printed on report cards (Fase 3 F).
    school_code: Mapped[str] = mapped_column(String(30), default="", server_default="")
    regional: Mapped[str] = mapped_column(String(80), default="", server_default="")
    district: Mapped[str] = mapped_column(String(80), default="", server_default="")
    revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class WriteLock(Base):
    """One row per serialized write domain (audit M7).

    Keys look like ``global:academic``; the prefix becomes the institution
    when Nexo turns multi-tenant, so locks never cross institutions.
    """

    __tablename__ = "write_locks"
    lock_key: Mapped[str] = mapped_column(String(120), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


SchoolYear.period_count = column_property(
    select(func.count(AcademicPeriod.period_id))
    .where(AcademicPeriod.school_year_id == SchoolYear.school_year_id)
    .correlate_except(AcademicPeriod)
    .scalar_subquery(),
    deferred=False,
)
