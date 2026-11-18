"""Database-backed sign-in throttling (audit M4).

Works with several workers and survives restarts. Two keys per attempt:
- ``pair:<ip>:<username>``: 5 failures in 15 minutes block that pair.
- ``ip:<ip>``: 30 failures in 15 minutes block the address.
The account itself is never locked globally, so an attacker cannot lock the
administrator out from another address.
"""

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.security_model import LoginThrottle

WINDOW = timedelta(minutes=15)
LIMITS = {"pair": 5, "ip": 30}
BLOCKED_MESSAGE = "Demasiados intentos de inicio de sesión. Inténtalo de nuevo en unos minutos"


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def throttle_keys(ip: str, username: str) -> dict[str, str]:
    return {"pair": f"pair:{ip}:{username.strip().casefold()}", "ip": f"ip:{ip}"}


def ensure_not_blocked(db: Session, ip: str, username: str) -> None:
    now = _now()
    blocked = (
        db.query(LoginThrottle.login_throttle_id)
        .filter(
            LoginThrottle.throttle_key.in_(throttle_keys(ip, username).values()),
            LoginThrottle.blocked_until > now,
        )
        .first()
    )
    if blocked:
        raise HTTPException(status_code=429, detail=BLOCKED_MESSAGE)


def _ensure_row(db: Session, key: str, now: datetime) -> None:
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    elif dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    else:  # pragma: no cover - other dialects are not supported in production
        if db.query(LoginThrottle).filter_by(throttle_key=key).first() is None:
            db.add(LoginThrottle(throttle_key=key, failures=0, window_started_at=now))
            db.flush()
        return
    db.execute(
        insert(LoginThrottle)
        .values(throttle_key=key, failures=0, window_started_at=now)
        .on_conflict_do_nothing(index_elements=["throttle_key"])
    )


def record_failure(db: Session, ip: str, username: str) -> None:
    now = _now()
    for kind, key in throttle_keys(ip, username).items():
        _ensure_row(db, key, now)
        # Restart an expired window, then count atomically.
        db.execute(
            update(LoginThrottle)
            .where(
                LoginThrottle.throttle_key == key, LoginThrottle.window_started_at <= now - WINDOW
            )
            .values(failures=0, window_started_at=now, blocked_until=None)
        )
        db.execute(
            update(LoginThrottle)
            .where(LoginThrottle.throttle_key == key)
            .values(failures=LoginThrottle.failures + 1)
        )
        db.execute(
            update(LoginThrottle)
            .where(LoginThrottle.throttle_key == key, LoginThrottle.failures >= LIMITS[kind])
            .values(blocked_until=now + WINDOW)
        )


def record_success(db: Session, ip: str, username: str) -> None:
    db.query(LoginThrottle).filter(
        LoginThrottle.throttle_key == throttle_keys(ip, username)["pair"]
    ).delete(synchronize_session=False)
