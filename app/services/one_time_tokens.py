"""Single-use links for password reset and invitations (audit M6).

The raw token only travels in the email; the database keeps its SHA-256.
Issuing a new token of the same purpose invalidates the previous ones.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.email_model import OneTimeToken

LIFETIMES = {"reset": timedelta(minutes=30), "invite": timedelta(hours=72)}
INVALID_LINK = "El enlace no es válido o ya venció. Solicita uno nuevo"


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def digest(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def issue_token(db: Session, user_id: int, purpose: str) -> str:
    now = _now()
    db.query(OneTimeToken).filter(
        OneTimeToken.user_id == user_id,
        OneTimeToken.purpose == purpose,
        OneTimeToken.used_at.is_(None),
    ).update({OneTimeToken.used_at: now}, synchronize_session=False)
    raw = secrets.token_urlsafe(32)
    db.add(
        OneTimeToken(
            user_id=user_id,
            purpose=purpose,
            token_hash=digest(raw),
            created_at=now,
            expires_at=now + LIFETIMES[purpose],
        )
    )
    return raw


def consume_token(db: Session, raw: str, purposes: tuple[str, ...]) -> OneTimeToken:
    """Mark the token used and return it, or fail with a single generic message."""
    # Read before the institution is known; the caller then sets it (Fase 4 A).
    token = (
        db.query(OneTimeToken)
        .filter_by(token_hash=digest(raw or ""))
        .execution_options(nexo_tenant_bypass=True)
        .first()
    )
    if (
        token is None
        or token.purpose not in purposes
        or token.used_at is not None
        or token.expires_at <= _now()
    ):
        raise HTTPException(400, INVALID_LINK)
    token.used_at = _now()
    return token
