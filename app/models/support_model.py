"""Support tickets between institutions and Nexo's team (Fase 5, step G6).

Global tables pointing to the institution. A ticket holds only what people
write in it: Nexo's team never opens the institution's records to answer.
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    support_ticket_id: Mapped[int] = mapped_column(primary_key=True)
    institution_id: Mapped[int] = mapped_column(
        ForeignKey("institutions.institution_id"), index=True
    )
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"), nullable=True)
    requester_name: Mapped[str] = mapped_column(String(150))
    requester_email: Mapped[str] = mapped_column(String(255), default="")
    subject: Mapped[str] = mapped_column(String(150))
    # uso | error | facturacion | datos | otro
    category: Mapped[str] = mapped_column(String(20), default="uso")
    priority: Mapped[str] = mapped_column(String(10), default="normal")  # normal | alta | urgente
    # open | in_progress | waiting | resolved | closed
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    messages: Mapped[list["SupportMessage"]] = relationship(
        order_by="SupportMessage.support_message_id", cascade="all, delete-orphan"
    )


class SupportMessage(Base):
    __tablename__ = "support_messages"

    support_message_id: Mapped[int] = mapped_column(primary_key=True)
    support_ticket_id: Mapped[int] = mapped_column(
        ForeignKey("support_tickets.support_ticket_id"), index=True
    )
    author_kind: Mapped[str] = mapped_column(String(12))  # institution | platform
    author_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"), nullable=True)
    author_platform_admin_id: Mapped[int | None] = mapped_column(
        ForeignKey("platform_admins.platform_admin_id"), nullable=True
    )
    author_name: Mapped[str] = mapped_column(String(150))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
