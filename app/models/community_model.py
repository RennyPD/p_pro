from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm import relationship as orm_relationship

from app.db.database import Base


class Guardian(Base):
    __tablename__ = "guardians"

    guardian_id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    telephone: Mapped[str] = mapped_column(String(30))
    address: Mapped[str] = mapped_column(String(255), default="")


class StudentGuardian(Base):
    __tablename__ = "student_guardians"
    __table_args__ = (UniqueConstraint("student_id", "guardian_id", name="uq_student_guardian"),)

    student_guardian_id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.student_id"))
    guardian_id: Mapped[int] = mapped_column(ForeignKey("guardians.guardian_id"))
    relationship: Mapped[str] = mapped_column(String(50))
    primary_contact: Mapped[bool] = mapped_column(Boolean, default=False)
    emergency_contact: Mapped[bool] = mapped_column(Boolean, default=False)
    authorized_pickup: Mapped[bool] = mapped_column(Boolean, default=False)
    guardian: Mapped[Guardian] = orm_relationship("Guardian")


class Announcement(Base):
    __tablename__ = "announcements"

    announcement_id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(150))
    body: Mapped[str] = mapped_column(Text)
    audience: Mapped[str] = mapped_column(String(20), default="all")
    section_id: Mapped[int | None] = mapped_column(ForeignKey("sections.section_id"), nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    published_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )


class Notification(Base):
    __tablename__ = "notifications"

    notification_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), index=True)
    title: Mapped[str] = mapped_column(String(150))
    body: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(30), default="general")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
