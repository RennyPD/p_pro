from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password: Mapped[str] = mapped_column(String(255))
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.role_id"))
    student_id: Mapped[int | None] = mapped_column(ForeignKey("students.student_id"), nullable=True)
    teacher_id: Mapped[int | None] = mapped_column(ForeignKey("teachers.teacher_id"), nullable=True)
    guardian_id: Mapped[int | None] = mapped_column(
        ForeignKey("guardians.guardian_id"), nullable=True
    )
    mfa_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_pending_secret: Mapped[str | None] = mapped_column(String(64))
    mfa_pending_until: Mapped[datetime | None] = mapped_column(DateTime)
    mfa_attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    mfa_attempt_window: Mapped[datetime | None] = mapped_column(DateTime)
    # Last accepted TOTP time step: a code is accepted only once.
    mfa_last_step: Mapped[int | None] = mapped_column(nullable=True)
    session_version: Mapped[int] = mapped_column(default=0, server_default="0")
    module_views: Mapped[list[str] | None] = mapped_column(JSON)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())

    role: Mapped["Role"] = relationship("Role", back_populates="users")
    student: Mapped["Student | None"] = relationship("Student")
    teacher: Mapped["Teacher | None"] = relationship("Teacher")
    guardian: Mapped["Guardian | None"] = relationship("Guardian")

    @property
    def role_name(self) -> str:
        return self.role.name.casefold()

    @property
    def role_label(self) -> str | None:
        return self.role.label

    @property
    def linked_person(self) -> str | None:
        if self.student:
            return f"{self.student.full_name} · {self.student.enrollment_number}"
        if self.teacher:
            name = f"{self.teacher.first_name} {self.teacher.last_name}"
            return f"{name} · {self.teacher.employee_code}" if self.teacher.employee_code else name
        if self.guardian:
            return f"{self.guardian.first_name} {self.guardian.last_name}"
        return None
