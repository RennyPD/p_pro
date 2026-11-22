"""Queue and deliver emails (audit M6).

- ``queue_email`` adds the message to ``email_outbox`` inside the caller's
  transaction. Nothing is sent if that transaction rolls back.
- ``deliver_pending`` sends what is due through the configured backend and is
  called after the commit (FastAPI background task) and by ``scripts/send_emails``
  for retries. Failures are retried with backoff and recorded per message.
"""

import json
import logging
import smtplib
import ssl
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from email.utils import make_msgid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import settings
from app.models.email_model import EmailOutbox

logger = logging.getLogger("nexo.email")
MAX_ATTEMPTS = 5
BATCH = 50


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def queue_email(
    db: Session,
    to: str | None,
    subject: str,
    text: str,
    html: str = "",
    *,
    category: str,
    user_id: int | None = None,
    dedupe_key: str | None = None,
) -> EmailOutbox | None:
    """Add an email to the outbox; returns None if there is no address or it is a duplicate."""
    if not to or "@" not in to:
        return None
    if dedupe_key is not None:
        pending = [
            item
            for item in db.new
            if isinstance(item, EmailOutbox) and item.dedupe_key == dedupe_key
        ]
        if pending or db.scalar(select(EmailOutbox.email_id).filter_by(dedupe_key=dedupe_key)):
            return None
    item = EmailOutbox(
        to_address=to.strip(),
        subject=subject[:200],
        body_text=text,
        body_html=html,
        category=category,
        user_id=user_id,
        dedupe_key=dedupe_key,
        status="pending",
        attempts=0,
        last_error="",
        created_at=_now(),
        next_attempt_at=_now(),
    )
    db.add(item)
    return item


def build_message(item: EmailOutbox) -> EmailMessage:
    message = EmailMessage()
    message["From"] = settings.email_from
    message["To"] = item.to_address
    message["Subject"] = item.subject
    message["Message-ID"] = make_msgid(domain=settings.email_from.rsplit("@", 1)[-1].strip(">"))
    message.set_content(item.body_text)
    if item.body_html:
        message.add_alternative(item.body_html, subtype="html")
    return message


def send(message: EmailMessage) -> None:
    """Deliver one message with the configured backend."""
    if settings.email_backend == "console":
        logger.info(
            json.dumps(
                {"to": message["To"], "subject": message["Subject"]},
                ensure_ascii=False,
            )
        )
        return
    host, port = settings.smtp_host, settings.smtp_port
    if settings.smtp_security == "ssl":
        client = smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=20)
    else:
        client = smtplib.SMTP(host, port, timeout=20)
    with client as connection:
        if settings.smtp_security == "starttls":
            connection.starttls(context=ssl.create_default_context())
        if settings.smtp_username:
            connection.login(settings.smtp_username, settings.smtp_password or "")
        connection.send_message(message)


def deliver_pending(bind, limit: int = BATCH) -> dict[str, int]:
    """Send pending emails that are due. Safe to call from several workers."""
    sent = failed = 0
    with Session(bind=bind) as db:
        query = (
            select(EmailOutbox)
            .where(EmailOutbox.status == "pending", EmailOutbox.next_attempt_at <= _now())
            .order_by(EmailOutbox.email_id)
            .limit(limit)
        )
        if db.get_bind().dialect.name == "postgresql":
            query = query.with_for_update(skip_locked=True)
        for item in db.scalars(query).all():
            item.attempts += 1
            try:
                send(build_message(item))
            except Exception as exc:  # noqa: BLE001 - any provider error is retried
                item.last_error = f"{type(exc).__name__}: {exc}"[:500]
                if item.attempts >= MAX_ATTEMPTS:
                    item.status = "failed"
                    failed += 1
                else:
                    item.next_attempt_at = _now() + timedelta(minutes=5 * 2 ** (item.attempts - 1))
                logger.warning("email.failed id=%s attempt=%s", item.email_id, item.attempts)
            else:
                item.status, item.sent_at, item.last_error = "sent", _now(), ""
                sent += 1
            db.commit()
    return {"sent": sent, "failed": failed}


def deliver_after_commit(background_tasks, db: Session) -> None:
    """Schedule delivery once the response is sent (the caller has committed)."""
    background_tasks.add_task(deliver_pending, db.get_bind())
