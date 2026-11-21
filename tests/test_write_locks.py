"""Audit M7: keyed write locks instead of one global row."""

import pytest
from db_support import TEST_DATABASE_URL, make_engine
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from test_write_audit import demo  # noqa: F401  (shared fixture)

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


def test_attendance_and_student_writes_take_the_academic_lock(demo):  # noqa: F811
    """Audit M2: attendance used to rely only on a unique index, not on the period lock."""
    from unittest.mock import patch

    from test_write_audit import a_student

    from app.models import Enrollment, User

    client, sessions, tokens = demo
    with sessions() as db:
        teacher = db.query(User).filter_by(username="demo.docente").one()
        enrollment = (
            db.query(Enrollment)
            .join(Enrollment.section)
            .filter_by(teacher_id=teacher.teacher_id)
            .filter(Enrollment.state == "enrolled")
            .first()
        )
        enrollment_id = enrollment.enrollment_id
    student_id, _ = a_student(sessions)
    taken = []

    def spy(db, domain, institution_id=None):
        taken.append(domain)
        return lock_scope(db, domain, institution_id)

    with patch("app.services.governance_workflow.lock_scope", side_effect=spy):
        created = client.post(
            "/attendances/",
            headers=tokens["admin"],
            json={
                "enrollment_id": enrollment_id,
                "present": True,
                "reason": "Pase de lista",
                "exception_reason": "Sesión extraordinaria de prueba",
            },
        )
        assert created.status_code == 200, created.text
        assert taken == ["academic"]
        taken.clear()
        edited = client.patch(
            f"/students/{student_id}", headers=tokens["admin"], json={"telephone": "8095550199"}
        )
        assert edited.status_code == 200, edited.text
        assert taken == ["academic"]
