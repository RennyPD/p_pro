from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.db.tenant import TenantMixin


class RefreshToken(TenantMixin, Base):
    __tablename__ = "refresh_tokens"
    # Migration 0004 created both a unique constraint and a unique index.
    __table_args__ = (UniqueConstraint("token_hash", name="refresh_tokens_token_hash_key"),)

    refresh_token_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Set when the token was exchanged for a new one; reuse after that is theft.
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class AuditLog(TenantMixin, Base):
    __tablename__ = "audit_logs"

    audit_log_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.user_id"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(80), index=True)
    resource: Mapped[str] = mapped_column(String(80))
    detail: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime)


class LoginThrottle(Base):
    """Failed sign-in counters shared by every worker (audit M4).

    Keys combine the client IP with the account name, or the IP alone, so a
    third party cannot lock somebody else's account from their own address.
    A future institution prefix fits in the key without a redesign.
    """

    __tablename__ = "login_throttles"

    login_throttle_id: Mapped[int] = mapped_column(primary_key=True)
    throttle_key: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    failures: Mapped[int] = mapped_column(default=0, server_default="0")
    window_started_at: Mapped[datetime] = mapped_column(DateTime)
    blocked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class RateLimit(Base):
    """Request counters per fixed window, shared by every worker (Fase 4 C, audit B7).

    Global (no institution column): the key already names the institution and
    account, or the client address for public routes.
    """

    __tablename__ = "rate_limits"

    rate_key: Mapped[str] = mapped_column(String(200), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime, index=True)
    hits: Mapped[int] = mapped_column(default=0, server_default="0")
