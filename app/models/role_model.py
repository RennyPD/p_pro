from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Role(Base):
    __tablename__ = "roles"

    role_id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    description: Mapped[str] = mapped_column(String(255))
    label: Mapped[str | None] = mapped_column(String(100))

    users: Mapped[list["User"]] = relationship("User", back_populates="role")

    @property
    def role_title(self) -> str:
        return self.label or {
            "admin": "Administración",
            "teacher": "Docencia",
            "student": "Estudiante",
            "guardian": "Tutoría",
        }.get(self.name.casefold(), self.name)
