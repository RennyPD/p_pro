"""Audit M7: keyed write locks instead of one global row."""

import pytest
from db_support import TEST_DATABASE_URL, make_engine
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from test_write_audit import demo  # noqa: F401  (shared fixture)

from app.db.database import Base
from app.services.write_locks import LockOrderError, lock_academic, lock_key, lock_scope


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
        section_id = enrollment.section_id
    student_id, _ = a_student(sessions)
    taken = []

    def spy(db, domain, institution_id=None):
        taken.append(domain)
        return lock_scope(db, domain, institution_id)

    fine = []

    def spy_fine(db, **keys):
        fine.append(keys)
        return lock_academic(db, **keys)

    with (
        patch("app.services.governance_workflow.lock_scope", side_effect=spy),
        patch("app.services.academic_locks.lock_academic", side_effect=spy_fine),
    ):
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
        # Attendance locks its section only (Fase 3 G), not the whole academic domain.
        assert taken == [] and fine == [{"sections": [section_id]}]
        taken.clear()
        edited = client.patch(
            f"/students/{student_id}", headers=tokens["admin"], json={"telephone": "8095550199"}
        )
        assert edited.status_code == 200, edited.text
        assert taken == ["academic"]


def test_fine_locks_keep_the_global_order(demo):  # noqa: F811
    """Fase 3 G (B6): period → section → student, by id; general exclusive only first."""
    _client, sessions, _tokens = demo
    with sessions() as db:
        lock_academic(db, sections=[5, 2], students=[9])
        lock_academic(db, sections=[2], students=[9])  # already held: no-op
        with pytest.raises(LockOrderError):
            lock_academic(db, sections=[7])  # a section after a student
        db.rollback()
        lock_academic(db, students=[9])
        with pytest.raises(LockOrderError):
            lock_academic(db, students=[3])  # a lower id after a higher one
        db.rollback()
        lock_academic(db, sections=[1])
        with pytest.raises(LockOrderError):
            lock_scope(db, "academic")  # exclusive general after a fine lock
        db.rollback()
        # After a commit or rollback the order starts over.
        lock_scope(db, "academic")
        lock_academic(db, sections=[2], students=[1])
        db.commit()
        keys = {row[0] for row in db.execute(text("SELECT lock_key FROM write_locks"))}
        assert {
            "global:academic",
            "global:academic:section:2",
            "global:academic:student:1",
        } <= keys


def pg_sessions():
    engine = make_engine()
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine)


def timeout(session):
    session.execute(text("SET LOCAL lock_timeout = '400ms'"))


@pytest.mark.skipif(TEST_DATABASE_URL is None, reason="Requiere PostgreSQL (bloqueo por fila)")
def test_different_sections_write_at_the_same_time_and_the_same_section_waits():
    engine, sessions = pg_sessions()
    holder, other = sessions(), sessions()
    try:
        lock_academic(holder, sections=[10], students=[1])
        timeout(other)
        lock_academic(other, sections=[11], students=[2])  # other section and student: no wait
        other.rollback()
        timeout(other)
        with pytest.raises(OperationalError):
            lock_academic(other, sections=[10])  # same section: waits
        other.rollback()
        timeout(other)
        with pytest.raises(OperationalError):
            lock_academic(other, sections=[12], students=[1])  # same student: waits
    finally:
        other.rollback()
        holder.rollback()
        other.close()
        holder.close()
        engine.dispose()


@pytest.mark.skipif(TEST_DATABASE_URL is None, reason="Requiere PostgreSQL (bloqueo por fila)")
def test_structural_writes_exclude_fine_ones_both_ways():
    engine, sessions = pg_sessions()
    first, second = sessions(), sessions()
    try:
        lock_academic(first, sections=[10])  # e.g. a grade being saved
        timeout(second)
        with pytest.raises(OperationalError):
            lock_scope(second, "academic")  # e.g. closing the period: waits
        second.rollback()
        first.rollback()
        lock_scope(first, "academic")  # closing the period
        timeout(second)
        with pytest.raises(OperationalError):
            lock_academic(second, sections=[99])  # any fine write waits for it
        second.rollback()
        first.rollback()
        # Two fine writers share the general key.
        lock_academic(first, sections=[1])
        timeout(second)
        lock_academic(second, sections=[2])
    finally:
        second.rollback()
        first.rollback()
        second.close()
        first.close()
        engine.dispose()


@pytest.mark.skipif(TEST_DATABASE_URL is None, reason="Requiere PostgreSQL (bloqueo por fila)")
def test_waitlist_promotion_skips_a_busy_student_instead_of_waiting():
    from app.services.write_locks import try_lock_student

    engine, sessions = pg_sessions()
    busy, promoter = sessions(), sessions()
    try:
        lock_academic(busy, students=[4])
        lock_academic(promoter, sections=[3])
        assert try_lock_student(promoter, 4) is False
        assert try_lock_student(promoter, 5) is True
    finally:
        promoter.rollback()
        busy.rollback()
        promoter.close()
        busy.close()
        engine.dispose()


def test_a_selection_locks_its_section_then_the_student(demo):  # noqa: F811
    from unittest.mock import patch

    from app.models import Section, User

    client, sessions, tokens = demo
    with sessions() as db:
        student = db.query(User).filter_by(username="demo.estudiante").one().student_id
        section = db.query(Section).order_by(Section.section_id.desc()).first().section_id
    calls = []

    def spy(db, **keys):
        calls.append(keys)
        return lock_academic(db, **keys)

    with patch("app.services.academic_locks.lock_academic", side_effect=spy):
        client.post(f"/academic/catalog/sections/{section}/select", headers=tokens["estudiante"])
    assert calls[0] == {"sections": [section], "students": [student]}
