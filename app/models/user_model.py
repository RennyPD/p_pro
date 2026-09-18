from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(primary_key=True, index=True)
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

    role: Mapped["Role"] = relationship("Role", back_populates="users")

    @property
    def role_name(self) -> str:
        return self.role.name.casefold()
