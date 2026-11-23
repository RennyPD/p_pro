"""Spanish email templates: plain text plus simple, accessible HTML (audit M6)."""

from dataclasses import dataclass
from html import escape

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.database import settings
from app.services.institution_profile import settings_of


@dataclass
class Email:
    subject: str
    text: str
    html: str


def institution_name(db: Session) -> str:
    row = settings_of(db)
    return row.institution_name if row else "Nexo Académico"


def app_link(path: str) -> str:
    """Absolute link to the interface; refuses to build broken links without APP_URL."""
    if not settings.app_url:
        raise HTTPException(
            503, "El envío de enlaces por correo no está configurado. Contacta a administración"
        )
    return settings.app_url.rstrip("/") + path


def optional_link(label: str, path: str) -> tuple[str, str] | None:
    """Button for notices: omitted (never an error) when APP_URL is not configured."""
    return (label, settings.app_url.rstrip("/") + path) if settings.app_url else None


def render(
    db: Session,
    subject: str,
    greeting: str,
    paragraphs: list[str],
    *,
    action: tuple[str, str] | None = None,
    footer: str = "",
) -> Email:
    institution = institution_name(db)
    lines = [greeting, "", *paragraphs]
    if action:
        lines += ["", f"{action[0]}: {action[1]}"]
    lines += ["", f"— {institution}"]
    if footer:
        lines += ["", footer]
    body = "".join(f"<p>{escape(p)}</p>" for p in paragraphs)
    button = (
        f'<p><a href="{escape(action[1])}" style="display:inline-block;padding:10px 18px;'
        f'background:#1d4ed8;color:#ffffff;border-radius:8px;text-decoration:none">'
        f"{escape(action[0])}</a></p>"
        f'<p style="font-size:12px;color:#555">Si el botón no funciona, copia este enlace: '
        f"{escape(action[1])}</p>"
        if action
        else ""
    )
    small = f'<p style="font-size:12px;color:#555">{escape(footer)}</p>' if footer else ""
    html = (
        '<div style="font-family:Arial,sans-serif;font-size:15px;color:#111;max-width:560px">'
        f"<p>{escape(greeting)}</p>{body}{button}"
        f"<p>— {escape(institution)}</p>{small}</div>"
    )
    return Email(subject=f"{subject} · {institution}", text="\n".join(lines), html=html)


def password_reset(db: Session, name: str, token: str) -> Email:
    return render(
        db,
        "Restablece tu contraseña",
        f"Hola, {name}:",
        [
            "Recibimos una solicitud para restablecer la contraseña de tu cuenta.",
            "El enlace vence en 30 minutos y solo funciona una vez.",
            "Si no fuiste tú, ignora este correo: tu contraseña no cambia.",
        ],
        action=("Elegir una contraseña nueva", app_link(f"/restablecer?token={token}")),
    )


def invitation(db: Session, name: str, username: str, token: str) -> Email:
    return render(
        db,
        "Activa tu cuenta",
        f"Hola, {name}:",
        [
            f"Te crearon una cuenta en {institution_name(db)}. Tu usuario es «{username}».",
            "Para entrar, elige tu contraseña. El enlace vence en 72 horas.",
        ],
        action=("Activar mi cuenta", app_link(f"/activar?token={token}")),
    )


PREFERENCES_FOOTER = (
    "Recibes este aviso porque está activado en tu cuenta. Puedes desactivarlo en "
    "Nexo, en «Mi seguridad» > «Avisos por correo»."
)


def announcement(db: Session, name: str, title: str, body: str) -> Email:
    return render(
        db,
        title,
        f"Hola, {name}:",
        [line for line in body.splitlines() if line.strip()] or [body],
        action=optional_link("Abrir Nexo", "/"),
        footer=PREFERENCES_FOOTER,
    )


def grades_published(
    db: Session,
    name: str,
    student: str,
    subject: str,
    assessment: str,
    value: float,
    own: bool,
) -> Email:
    whose = "Tienes" if own else f"{student} tiene"
    return render(
        db,
        f"Nota publicada: {subject}",
        f"Hola, {name}:",
        [
            f"{whose} una nota nueva en {subject}.",
            f"{assessment}: {value:g}",
        ],
        action=optional_link("Ver las notas", "/my-grades" if own else "/guardian"),
        footer=PREFERENCES_FOOTER,
    )


def due_reminder(
    db: Session,
    name: str,
    student: str,
    concept: str,
    amount: str,
    due: str,
    phase: str,
    own: bool,
) -> Email:
    whose = "tu cuenta" if own else f"la cuenta de {student}"
    if phase == "before":
        subject, first = "Pago próximo a vencer", f"El {due} vence un pago de {whose}."
    else:
        subject, first = "Pago vencido", f"Un pago de {whose} venció el {due} y sigue pendiente."
    return render(
        db,
        subject,
        f"Hola, {name}:",
        [first, f"{concept}: {amount}", "Si ya pagaste, ignora este aviso."],
        action=optional_link("Ver la cuenta", "/my-finance" if own else "/guardian"),
        footer=PREFERENCES_FOOTER,
    )
