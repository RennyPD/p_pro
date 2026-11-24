"""Keyed write serialization (audit M7, finding B6).

``lock_scope(db, domain)`` takes a row lock on ``write_locks`` for the rest of
the transaction (PostgreSQL row lock; SQLite serializes the writer). Domains:

- ``academic``: periods, sections, enrollments, grades, attendance, operations.
- ``access``: users, roles, permissions and module grants.
- ``finance``: postings, approvals, reversals and cash closings.

Always take several domains in alphabetical order to avoid deadlocks.

Academic writes are finer since Fase 3 G (B6). ``lock_academic`` takes, always
in this order:

1. the general academic key in *shared* mode (``FOR SHARE``), so structural
   operations, which take it exclusively through ``lock_scope(db, "academic")``,
   never overlap a fine-grained write;
2. period keys, 3. section keys and 4. student keys, each level sorted by id.

Grades, attendance, assessments and tasks lock their section; selections lock
the section (capacity) and the student (credits, schedule). Asking for a key
of a lower level after a higher one, or for the exclusive general key after
any fine key, raises ``LockOrderError``: that order could deadlock.
"""

from sqlalchemy import event, text, update
from sqlalchemy.orm import Session

from app.models.configuration_model import WriteLock
from app.services.billing.access import ensure_writable

DOMAINS = frozenset({"academic", "access", "finance", "platform"})


def _tenant_of(db: Session, institution_id: int | None) -> int | None:
    """Locks belong to the session's institution unless one is given (Fase 4 A)."""
    if institution_id is not None:
        return institution_id
    from app.db.tenant import current_tenant

    return current_tenant(db)


def lock_key(domain: str, institution_id: int | None = None) -> str:
    if domain not in DOMAINS:
        raise ValueError(f"Dominio de bloqueo desconocido: {domain}")
    return f"{institution_id if institution_id is not None else 'global'}:{domain}"


class LockOrderError(RuntimeError):
    """Locks requested in an order that could deadlock (programming error)."""


LEVELS = ("period", "section", "student")
STATE = "nexo_academic_locks"


def _state(db: Session) -> dict:
    return db.info.setdefault(STATE, {"general": None, "level": -1, "last": {}, "held": set()})


@event.listens_for(Session, "after_commit")
@event.listens_for(Session, "after_rollback")
def _reset_locks(session: Session, *_args) -> None:
    session.info.pop(STATE, None)


def _ensure_row(db: Session, key: str) -> str:
    """Make sure the key's row exists; returns the dialect.

    On PostgreSQL a missing row is created in its own committed transaction:
    inserting it inside the caller's transaction would make every other writer
    of the same new key wait on that uncommitted insert, not on the row lock.
    """
    bind = db.get_bind()
    dialect = bind.dialect.name
    if dialect == "postgresql":
        exists = db.execute(
            text("SELECT 1 FROM write_locks WHERE lock_key = :key"), {"key": key}
        ).first()
        if exists is None:
            from sqlalchemy.dialects.postgresql import insert

            engine = getattr(bind, "engine", bind)
            with engine.connect() as connection:
                connection.execute(
                    insert(WriteLock).values(lock_key=key, version=0).on_conflict_do_nothing()
                )
                connection.commit()
    elif dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert

        db.execute(insert(WriteLock).values(lock_key=key, version=0).on_conflict_do_nothing())
    elif db.get(WriteLock, key) is None:  # pragma: no cover - unsupported dialects
        db.add(WriteLock(lock_key=key, version=0))
        db.flush()
    return dialect


def _exclusive(db: Session, key: str) -> None:
    _ensure_row(db, key)
    db.execute(
        update(WriteLock).where(WriteLock.lock_key == key).values(version=WriteLock.version + 1)
    )


def lock_academic(
    db: Session,
    *,
    periods=(),
    sections=(),
    students=(),
    institution_id: int | None = None,
) -> None:
    """Fine-grained academic locks in the global order (see the module docstring)."""
    ensure_writable(db)
    state = _state(db)
    general = lock_key("academic", _tenant_of(db, institution_id))
    if state["general"] is None:
        dialect = _ensure_row(db, general)
        if dialect == "postgresql":
            db.execute(
                text("SELECT lock_key FROM write_locks WHERE lock_key = :key FOR SHARE"),
                {"key": general},
            )
        state["general"] = "shared"
    acquired = False
    for level, ids in zip(range(len(LEVELS)), (periods, sections, students)):
        wanted = sorted({int(i) for i in ids if i is not None})
        new = [i for i in wanted if (LEVELS[level], i) not in state["held"]]
        if not new:
            continue
        if level < state["level"] or (
            level == state["level"] and new[0] < state["last"].get(level, -1)
        ):
            raise LockOrderError(
                f"Bloqueo {LEVELS[level]} {new[0]} pedido fuera de orden "
                "(período → sección → estudiante, por id)"
            )
        for identifier in new:
            _exclusive(db, f"{general}:{LEVELS[level]}:{identifier}")
            state["held"].add((LEVELS[level], identifier))
        state["level"] = level
        state["last"][level] = new[-1]
        acquired = True
    if acquired or state["general"] == "shared":
        db.expire_all()


def try_lock_student(db: Session, student_id: int, institution_id: int | None = None) -> bool:
    """Lock a student only if free right now (never waits, so it cannot deadlock).

    Used when promoting from a waitlist: a candidate busy in another selection
    keeps their place and is considered on the next promotion.
    """
    state = _state(db)
    if ("student", student_id) in state["held"]:
        return True
    key = f"{lock_key('academic', _tenant_of(db, institution_id))}:student:{student_id}"
    if _ensure_row(db, key) == "postgresql":
        row = db.execute(
            text("SELECT lock_key FROM write_locks WHERE lock_key = :key FOR UPDATE SKIP LOCKED"),
            {"key": key},
        ).first()
        if row is None:
            return False
    else:
        _exclusive(db, key)
    state["held"].add(("student", student_id))
    return True


def lock_scope(db: Session, domain: str, institution_id: int | None = None) -> None:
    ensure_writable(db)  # read-only institutions (Fase 4 D3)
    key = lock_key(domain, _tenant_of(db, institution_id))
    if domain == "academic":
        state = _state(db)
        if state["held"] or state["general"] == "shared":
            raise LockOrderError(
                "El bloqueo académico general se pide antes que cualquier bloqueo fino"
            )
        state["general"] = "exclusive"
    _exclusive(db, key)
    db.expire_all()


def lock_access(db: Session) -> None:
    lock_scope(db, "access")
