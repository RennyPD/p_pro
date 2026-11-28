"""Responses of the support tickets (Fase 5, step G6)."""

from datetime import datetime

from pydantic import BaseModel


class TicketMessageOut(BaseModel):
    support_message_id: int
    author_kind: str
    author_name: str
    body: str
    created_at: datetime


class TicketOut(BaseModel):
    support_ticket_id: int
    subject: str
    category: str
    priority: str
    status: str
    requester_name: str
    created_at: datetime
    updated_at: datetime
    messages: list[TicketMessageOut] | None = None


class PlatformTicketOut(TicketOut):
    institution: str = ""
    requester_email: str | None = None
