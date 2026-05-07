from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base

class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password: Mapped[str] = mapped_column(String(255))
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.role_id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("students.student_id"), nullable=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.teacher_id"), nullable=True)

    role: Mapped["Role"] = relationship("Role", back_populates="users")