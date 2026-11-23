"""Email outbox and one-time links (audit M6).

Emails are queued in the same transaction as the event that causes them, so a
rolled-back change sends nothing and a committed one is never lost; delivery
happens after the commit and is retried by ``scripts/send_emails``.
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.db.tenant import TenantMixin


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class EmailOutbox(TenantMixin, Base):
    __tablename__ = "email_outbox"

    email_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True, index=True
    )
    to_address: Mapped[str] = mapped_column(String(320))
    subject: Mapped[str] = mapped_column(String(200))
    body_text: Mapped[str] = mapped_column(Text)
    body_html: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(30), index=True)
    # Prevents the same notice twice (e.g. "due:charge:12:before"). Ready to be
    # prefixed with the institution when the system becomes multi-tenant.
    dedupe_key: Mapped[str | None] = mapped_column(String(200), unique=True, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class OneTimeToken(TenantMixin, Base):
    """Password reset or invitation link. Only the SHA-256 of the token is stored."""

    __tablename__ = "one_time_tokens"

    token_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), index=True
    )
    purpose: Mapped[str] = mapped_column(String(20))  # reset | invite
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
