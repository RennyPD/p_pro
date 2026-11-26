"""Acceptances of the legal documents (Fase 5, step G3). Global table."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


def now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class LegalAcceptance(Base):
    __tablename__ = "legal_acceptances"

    legal_acceptance_id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), index=True)
    version: Mapped[str] = mapped_column(String(20))
    institution_id: Mapped[int | None] = mapped_column(
        ForeignKey("institutions.institution_id"), nullable=True, index=True
    )
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"), nullable=True)
    accepted_by: Mapped[str] = mapped_column(String(255), default="")  # email or username
    ip: Mapped[str] = mapped_column(String(64), default="")
    accepted_at: Mapped[datetime] = mapped_column(DateTime, default=now)
