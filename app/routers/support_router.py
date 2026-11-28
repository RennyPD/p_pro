"""Support tickets of the institution's accounts (Fase 5, step G6)."""

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_user, has_permission
from app.db.Session import get_db
from app.models.support_model import SupportTicket
from app.models.user_model import User
from app.pagination import page_query
from app.schemas.support_schema import TicketOut
from app.services import support
from app.services.audit_log import record
from app.services.billing.access import allow_while_read_only
from app.services.demo import refuse_in_demo
from app.services.rate_limit import SUPPORT, per_account
from app.services.write_locks import lock_access

router = APIRouter(prefix="/support", tags=["support"])


class TicketIn(BaseModel):
    subject: str = Field(min_length=4, max_length=150)
    category: str = Field(pattern=r"^(uso|error|facturacion|datos|otro)$")
    priority: str = Field(default="normal", pattern=r"^(normal|alta|urgente)$")
    body: str = Field(min_length=10, max_length=5000)


class MessageIn(BaseModel):
    body: str = Field(min_length=2, max_length=5000)


def visible(db: Session, user: User):
    """Own tickets; the institution's administration sees all of them."""
    query = db.query(SupportTicket).filter(SupportTicket.institution_id == user.institution_id)
    if not has_permission(user, "settings.manage"):
        query = query.filter(SupportTicket.user_id == user.user_id)
    return query


def ticket_or_404(db: Session, user: User, ticket_id: int) -> SupportTicket:
    ticket = visible(db, user).filter(SupportTicket.support_ticket_id == ticket_id).first()
    if ticket is None:
        raise HTTPException(404, "Ticket no encontrado")
    return ticket


@router.get("/tickets", response_model=list[TicketOut])
def list_tickets(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = visible(db, user).order_by(SupportTicket.updated_at.desc())
    return [support.ticket_out(ticket) for ticket in page_query(query, response, skip, limit)]


@router.post("/tickets", response_model=TicketOut, dependencies=[Depends(per_account(SUPPORT))])
def open_ticket(
    data: TicketIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    refuse_in_demo(db, "El soporte")
    allow_while_read_only(db)  # an unpaid institution can still ask for help
    lock_access(db)
    ticket = support.create_ticket(db, user, data.subject, data.category, data.priority, data.body)
    record(db, user, "support.opened", f"support:{ticket.support_ticket_id}", ticket.subject)
    db.commit()
    return support.ticket_out(ticket, with_messages=True)


@router.get("/tickets/{ticket_id}", response_model=TicketOut)
def get_ticket(
    ticket_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    return support.ticket_out(ticket_or_404(db, user, ticket_id), with_messages=True)


@router.post(
    "/tickets/{ticket_id}/messages",
    response_model=TicketOut,
    dependencies=[Depends(per_account(SUPPORT))],
)
def reply(
    ticket_id: int,
    data: MessageIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    refuse_in_demo(db, "El soporte")
    allow_while_read_only(db)
    lock_access(db)
    ticket = ticket_or_404(db, user, ticket_id)
    support.institution_reply(db, ticket, user, data.body)
    record(db, user, "support.replied", f"support:{ticket_id}", "Mensaje al equipo de Nexo")
    db.commit()
    return support.ticket_out(ticket, with_messages=True)
