from datetime import date

from sqlalchemy import Boolean, Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class AcademicPeriod(Base):
    __tablename__ = "academic_periods"

    period_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, default=False)


class InstitutionSettings(Base):
    __tablename__ = "institution_settings"

    settings_id: Mapped[int] = mapped_column(primary_key=True, default=1)
    institution_name: Mapped[str] = mapped_column(String(150), default="Nexo Académico")
    enrollment_prefix: Mapped[str] = mapped_column(String(20), default="EST")
    enrollment_digits: Mapped[int] = mapped_column(Integer, default=4)
    next_enrollment_number: Mapped[int] = mapped_column(Integer, default=1)
    passing_grade: Mapped[float] = mapped_column(default=70.0)
