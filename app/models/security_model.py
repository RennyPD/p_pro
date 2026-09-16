from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    refresh_token_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    audit_log_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.user_id"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(80), index=True)
    resource: Mapped[str] = mapped_column(String(80))
    detail: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime)
