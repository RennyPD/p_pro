from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class StudentAccount(Base):
    __tablename__ = "student_accounts"

    student_account_id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.student_id"), unique=True)
    cutoff_day: Mapped[int] = mapped_column(Integer, default=15)
    due_day: Mapped[int] = mapped_column(Integer, default=30)
    student: Mapped["Student"] = relationship("Student")
    charges: Mapped[list["Charge"]] = relationship("Charge", cascade="all, delete-orphan")
    payments: Mapped[list["Payment"]] = relationship("Payment", cascade="all, delete-orphan")


class Charge(Base):
    __tablename__ = "charges"

    charge_id: Mapped[int] = mapped_column(primary_key=True)
    student_account_id: Mapped[int] = mapped_column(
        ForeignKey("student_accounts.student_account_id")
    )
    description: Mapped[str] = mapped_column(String(200))
    amount: Mapped[float] = mapped_column(Float)
    due_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )


class Payment(Base):
    __tablename__ = "payments"

    payment_id: Mapped[int] = mapped_column(primary_key=True)
    student_account_id: Mapped[int] = mapped_column(
        ForeignKey("student_accounts.student_account_id")
    )
    amount: Mapped[float] = mapped_column(Float)
    reference: Mapped[str] = mapped_column(String(100))
    note: Mapped[str] = mapped_column(String(250), default="")
    paid_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )
