from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.security_model import RefreshToken
from app.models.user_model import User


def lock_account(db: Session, user: User) -> User:
    # The write serializes changes on SQLite and takes the row lock on PostgreSQL.
    user_id, version = user.user_id, user.session_version
    matched = db.execute(
        update(User)
        .where(User.user_id == user_id, User.session_version == version)
        .values(session_version=User.session_version)
    )
    if matched.rowcount != 1:
        raise HTTPException(401, "La sesión se revocó. Inicia sesión de nuevo")
    return db.get(User, user_id, populate_existing=True)


def revoke_account_sessions(db: Session, user: User):
    user.session_version += 1
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user.user_id, RefreshToken.revoked_at.is_(None)
    ).update({"revoked_at": datetime.now(UTC).replace(tzinfo=None)})
    user.mfa_pending_secret = None
    user.mfa_pending_until = None
