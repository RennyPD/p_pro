"""Request limits per account or address (Fase 4 C, audit B7).

Fixed windows counted in ``rate_limits`` (PostgreSQL in production), so every
worker and replica shares them without Redis. Each hit is counted in its own
short transaction, committed at once: a request that fails afterwards still
counts, and the count never waits for the request's own locks.

Routes declare a limit with ``dependencies=[Depends(per_account(UPLOADS))]``
(signed-in routes, key ``<institution>:<account>``) or ``per_address(...)``
(public routes, key = client address). Over the limit: 429 with a Spanish
message and ``Retry-After``.
"""

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, Request
from sqlalchemy import Engine, case, delete
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db.database import settings
from app.db.Session import get_db
from app.models.security_model import RateLimit
from app.models.user_model import User


@dataclass(frozen=True)
class Limit:
    name: str
    hits: int
    seconds: int
    message: str


UPLOADS = Limit(
    "uploads", 30, 600, "Subiste demasiados archivos en poco tiempo. Espera unos minutos"
)
EXPORTS = Limit(
    "exports", 60, 600, "Generaste demasiados documentos en poco tiempo. Espera unos minutos"
)
IMPORTS = Limit(
    "imports", 10, 3600, "Hiciste demasiadas importaciones en la última hora. Espera un poco"
)
PUBLIC = Limit("public", 60, 60, "Demasiadas consultas. Espera un minuto")
SIGNUP = Limit(
    "signup", 5, 3600, "Demasiados registros desde esta dirección. Inténtalo en una hora"
)
PLATFORM_LOGIN = Limit(
    "platform-login", 10, 900, "Demasiados intentos de inicio de sesión. Espera unos minutos"
)


def now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def client_ip(request: Request) -> str:
    # Behind a proxy, run uvicorn with --proxy-headers and FORWARDED_ALLOW_IPS.
    return request.client.host if request.client else "desconocida"


def window_of(limit: Limit, moment: datetime) -> datetime:
    epoch = int(moment.replace(tzinfo=UTC).timestamp())
    return datetime.fromtimestamp(epoch - epoch % limit.seconds, UTC).replace(tzinfo=None)


def _upsert(bind: Engine, key: str, start: datetime) -> int:
    dialect = bind.dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    table = RateLimit.__table__
    statement = insert(table).values(rate_key=key, window_start=start, hits=1)
    same_window = table.c.window_start == start
    statement = statement.on_conflict_do_update(
        index_elements=[table.c.rate_key],
        set_={
            # A new window restarts the count; the same window adds one.
            "hits": case((same_window, table.c.hits + 1), else_=1),
            "window_start": start,
        },
    ).returning(table.c.hits)
    with bind.connect() as connection:
        hits = connection.execute(statement).scalar_one()
        connection.commit()
    return hits


def hit(db: Session, limit: Limit, subject: str, moment: datetime | None = None) -> None:
    if not settings.rate_limits_enabled:
        return
    moment = moment or now()
    start = window_of(limit, moment)
    hits = _upsert(db.get_bind(), f"{limit.name}:{subject}"[:200], start)
    if hits > limit.hits:
        wait = math.ceil((start + timedelta(seconds=limit.seconds) - moment).total_seconds())
        raise HTTPException(429, limit.message, headers={"Retry-After": str(max(1, wait))})


def per_account(limit: Limit):
    def dependency(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
        hit(db, limit, f"{user.institution_id}:{user.user_id}")

    dependency.rate_limit = limit
    return dependency


def per_address(limit: Limit):
    def dependency(request: Request, db: Session = Depends(get_db)):
        hit(db, limit, client_ip(request))

    dependency.rate_limit = limit
    return dependency


def purge(bind: Engine, older_than: timedelta = timedelta(days=1)) -> int:
    """Forget windows that ended long ago (run by the daily jobs)."""
    with bind.connect() as connection:
        count = connection.execute(
            delete(RateLimit).where(RateLimit.window_start < now() - older_than)
        ).rowcount
        connection.commit()
    return count
