from datetime import date

from sqlalchemy import Boolean, Date, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


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
    academic_year: Mapped[str] = mapped_column(String(20), default="")
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
    revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class GovernanceControl(Base):
    __tablename__ = "governance_control"
    governance_control_id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=0)
