"""Keyed write serialization (audit M7).

``lock_scope(db, domain)`` takes a row lock on ``write_locks`` for the rest of
the transaction (PostgreSQL row lock; SQLite serializes the writer). Domains:

- ``academic``: periods, sections, enrollments, grades, attendance, operations.
  Kept together because their invariants cross (closing a period vs. grade
  writes, capacity vs. selections).
- ``access``: users, roles, permissions and module grants.
- ``finance``: postings, approvals, reversals and cash closings.

Always take several domains in alphabetical order to avoid deadlocks.
"""

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.configuration_model import WriteLock

DOMAINS = frozenset({"academic", "access", "finance"})


def lock_key(domain: str, institution_id: int | None = None) -> str:
    if domain not in DOMAINS:
        raise ValueError(f"Dominio de bloqueo desconocido: {domain}")
    return f"{institution_id if institution_id is not None else 'global'}:{domain}"


def lock_scope(db: Session, domain: str, institution_id: int | None = None) -> None:
    key = lock_key(domain, institution_id)
    dialect = db.get_bind().dialect.name
    if dialect in {"sqlite", "postgresql"}:
        if dialect == "sqlite":
            from sqlalchemy.dialects.sqlite import insert
        else:
            from sqlalchemy.dialects.postgresql import insert
        db.execute(insert(WriteLock).values(lock_key=key, version=0).on_conflict_do_nothing())
    elif db.get(WriteLock, key) is None:  # pragma: no cover - unsupported dialects
        db.add(WriteLock(lock_key=key, version=0))
        db.flush()
    db.execute(
        update(WriteLock).where(WriteLock.lock_key == key).values(version=WriteLock.version + 1)
    )
    db.expire_all()


def lock_access(db: Session) -> None:
    lock_scope(db, "access")
