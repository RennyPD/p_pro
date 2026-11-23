"""Institutions: the tenants of the SaaS (Fase 4, block A)."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, String, event, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Institution(Base):
    __tablename__ = "institutions"

    institution_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    # Used for the subdomain and as the sign-in code (block B).
    slug: Mapped[str] = mapped_column(String(60), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | suspended
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )
    # Fase 4 B: contact and the reason of the last suspension or reactivation.
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status_reason: Mapped[str | None] = mapped_column(String(250), nullable=True)
    status_changed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


@event.listens_for(Institution.__table__, "after_create")
def _first_institution(target, connection, **_kwargs) -> None:
    """Databases built with create_all (development, tests) start with institution 1."""
    connection.execute(
        text(
            "INSERT INTO institutions (institution_id, name, slug, status, created_at) "
            "VALUES (1, 'Institución principal', 'principal', 'active', CURRENT_TIMESTAMP)"
        )
    )
