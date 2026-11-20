from sqlalchemy import String, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Role(Base):
    __tablename__ = "roles"

    role_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    description: Mapped[str] = mapped_column(String(255))
    label: Mapped[str | None] = mapped_column(String(100))
    # Which records the role's permissions reach: institution | sections | own | linked.
    scope: Mapped[str] = mapped_column(
        String(20), default="institution", server_default="institution"
    )

    users: Mapped[list["User"]] = relationship("User", back_populates="role")

    @property
    def role_title(self) -> str:
        return self.label or {
            "admin": "Administración",
            "teacher": "Docencia",
            "student": "Estudiante",
            "guardian": "Tutoría",
        }.get(self.name.casefold(), self.name)


@event.listens_for(Role, "before_insert")
def _default_scope(_mapper, _connection, role: Role) -> None:
    """Built-in roles created without a scope get theirs (teacher -> sections, ...)."""
    if not role.scope:
        from app.permissions import default_scope

        role.scope = default_scope(role.name)
