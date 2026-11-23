"""Platform (super administration) accounts and their audit (Fase 4 B).

Global tables: they belong to no institution and never mix with institution
accounts (separate table, tokens with scope "platform", own dependency).
A second factor (TOTP) is mandatory and set when the account is created.
"""

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class PlatformAdmin(Base):
    __tablename__ = "platform_admins"

    platform_admin_id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(150))
    password: Mapped[str] = mapped_column(String(255))
    mfa_secret: Mapped[str] = mapped_column(String(64))
    # Last accepted TOTP step: a code is never accepted twice.
    mfa_last_step: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    session_version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class PlatformAuditLog(Base):
    __tablename__ = "platform_audit_logs"

    platform_audit_log_id: Mapped[int] = mapped_column(primary_key=True)
    platform_admin_id: Mapped[int | None] = mapped_column(
        ForeignKey("platform_admins.platform_admin_id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(80))
    resource: Mapped[str] = mapped_column(String(120))
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
