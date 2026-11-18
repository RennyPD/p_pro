"""Audit M7: keyed write locks instead of one global row."""

import pytest
from db_support import TEST_DATABASE_URL, make_engine
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.services.write_locks import lock_key, lock_scope


def test_lock_keys_are_ready_for_institutions():
    assert lock_key("academic") == "global:academic"
    assert lock_key("finance", institution_id=7) == "7:finance"
    with pytest.raises(ValueError):
        lock_key("todo")


@pytest.mark.skipif(TEST_DATABASE_URL is None, reason="Requiere PostgreSQL (bloqueo por fila)")
def test_access_writes_do_not_wait_for_academic_writes():
    engine = make_engine()
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    holder, other = sessions(), sessions()
    try:
        lock_scope(holder, "academic")  # held until holder commits
        other.execute(text("SET LOCAL lock_timeout = '500ms'"))
        lock_scope(other, "access")  # different key: no wait
        other.rollback()
        other.execute(text("SET LOCAL lock_timeout = '500ms'"))
        with pytest.raises(OperationalError):
            lock_scope(other, "academic")  # same key: blocked
    finally:
        other.rollback()
        holder.rollback()
        other.close()
        holder.close()
        engine.dispose()
