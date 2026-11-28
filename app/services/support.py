"""Support tickets (Fase 5, step G6).

- Any account opens tickets and follows its own; whoever administers the
  institution (``settings.manage``) sees all of the institution's tickets.
- Nexo's team answers from the platform panel; each answer emails the person
  who opened the ticket, and each message from the institution emails
  SUPPORT_EMAIL. Works in read-only mode; not in the public demo.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.database import settings
from app.models.support_model import SupportMessage, SupportTicket, now

CATEGORIES = {
    "uso": "Cómo usar Nexo",
    "error": "Algo no funciona",
    "facturacion": "Plan y facturación",
    "datos": "Datos y privacidad",
    "otro": "Otro",
}
STATUSES = {
    "open": "Abierto",
    "in_progress": "En revisión",
    "waiting": "Esperando tu respuesta",
    "resolved": "Resuelto",
    "closed": "Cerrado",
}


def display_name(user) -> str:
    return user.username


def create_ticket(db: Session, user, subject: str, category: str, priority: str, body: str):
    ticket = SupportTicket(
        institution_id=user.institution_id,
        user_id=user.user_id,
        requester_name=display_name(user),
        requester_email=user.email or "",
        subject=subject.strip(),
        category=category,
        priority=priority,
        status="open",
        created_at=now(),
        updated_at=now(),
    )
    ticket.messages.append(
        SupportMessage(
            author_kind="institution",
            author_user_id=user.user_id,
            author_name=display_name(user),
            body=body.strip(),
            created_at=now(),
        )
    )
    db.add(ticket)
    db.flush()
    notify_team(db, ticket, body)
    return ticket


def institution_reply(db: Session, ticket: SupportTicket, user, body: str) -> SupportMessage:
    if ticket.status == "closed":
        raise HTTPException(409, "El ticket está cerrado. Abre uno nuevo si necesitas ayuda")
    message = SupportMessage(
        author_kind="institution",
        author_user_id=user.user_id,
        author_name=display_name(user),
        body=body.strip(),
        created_at=now(),
    )
    ticket.messages.append(message)
    ticket.status = "open"  # back to the team, also after «resuelto»
    ticket.updated_at = now()
    db.flush()
    notify_team(db, ticket, body)
    return message


def team_reply(db: Session, ticket: SupportTicket, admin, body: str, status: str) -> SupportMessage:
    message = SupportMessage(
        author_kind="platform",
        author_platform_admin_id=admin.platform_admin_id,
        author_name=f"{admin.name} (equipo de Nexo)",
        body=body.strip(),
        created_at=now(),
    )
    ticket.messages.append(message)
    ticket.status = status
    ticket.updated_at = now()
    db.flush()
    notify_requester(db, ticket, body)
    return message


def notify_team(db: Session, ticket: SupportTicket, body: str) -> None:
    from app.services.email_service import queue_email

    if not settings.support_email:
        return
    queue_email(
        db,
        settings.support_email,
        f"[Soporte #{ticket.support_ticket_id}] {ticket.subject}",
        f"{ticket.requester_name} ({CATEGORIES.get(ticket.category)}, prioridad {ticket.priority}):\n\n"
        f"{body.strip()}\n\nResponde desde el panel de plataforma.",
        category="support",
    )


def notify_requester(db: Session, ticket: SupportTicket, body: str) -> None:
    from app.db.tenant import current_tenant, set_tenant
    from app.services.email_service import queue_email
    from app.services.email_templates import optional_link, render

    if not ticket.requester_email:
        return
    if current_tenant(db) is None:
        set_tenant(db, ticket.institution_id)  # the email carries the institution's name
    message = render(
        db,
        f"Respuesta a tu ticket #{ticket.support_ticket_id}",
        f"Hola, {ticket.requester_name}:",
        [
            f"El equipo de Nexo respondió a «{ticket.subject}»:",
            *[line for line in body.strip().splitlines() if line.strip()],
            f"Estado: {STATUSES.get(ticket.status, ticket.status)}.",
        ],
        action=optional_link("Ver el ticket", f"/support/{ticket.support_ticket_id}"),
    )
    queue_email(
        db,
        ticket.requester_email,
        message.subject,
        message.text,
        message.html,
        category="support",
        user_id=ticket.user_id,
    )


def ticket_out(ticket: SupportTicket, with_messages: bool = False) -> dict:
    out = {
        "support_ticket_id": ticket.support_ticket_id,
        "subject": ticket.subject,
        "category": ticket.category,
        "priority": ticket.priority,
        "status": ticket.status,
        "requester_name": ticket.requester_name,
        "created_at": ticket.created_at.isoformat(),
        "updated_at": ticket.updated_at.isoformat(),
    }
    if with_messages:
        out["messages"] = [
            {
                "support_message_id": message.support_message_id,
                "author_kind": message.author_kind,
                "author_name": message.author_name,
                "body": message.body,
                "created_at": message.created_at.isoformat(),
            }
            for message in ticket.messages
        ]
    return out
