"""Email outbox, delivery and single-use links (audit M6)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from db_support import make_engine
from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models import EmailOutbox, OneTimeToken, Role, User
from app.services import email_service
from app.services.email_service import deliver_pending, queue_email
from app.services.one_time_tokens import consume_token, issue_token


@pytest.fixture
def sessions(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'email.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        role = Role(name="admin", description="Administración")
        db.add(role)
        db.flush()
        db.add(User(username="ana", email="ana@example.com", password="x", role_id=role.role_id))
        db.commit()
    yield factory
    engine.dispose()


def user_id(sessions):
    with sessions() as db:
        return db.query(User).filter_by(username="ana").one().user_id


def statuses(sessions):
    with sessions() as db:
        return [
            (e.status, e.attempts) for e in db.query(EmailOutbox).order_by(EmailOutbox.email_id)
        ]


# Paso 1: bandeja de salida.


def test_queued_email_is_sent_after_commit_and_never_for_a_rollback(sessions):
    with sessions() as db:
        queue_email(db, "ana@example.com", "Hola", "Texto", category="test")
        db.rollback()
    with sessions() as db:
        queue_email(db, "ana@example.com", "Hola", "Texto", "<p>Texto</p>", category="test")
        db.commit()
        bind = db.get_bind()
    assert statuses(sessions) == [("pending", 0)]
    with patch.object(email_service, "send") as send:
        assert deliver_pending(bind) == {"sent": 1, "failed": 0}
    message = send.call_args.args[0]
    assert message["To"] == "ana@example.com" and message["Subject"] == "Hola"
    assert statuses(sessions) == [("sent", 1)]
    assert deliver_pending(bind) == {"sent": 0, "failed": 0}


def test_duplicates_and_missing_addresses_are_skipped(sessions):
    with sessions() as db:
        assert queue_email(db, "ana@example.com", "A", "x", category="t", dedupe_key="k1")
        assert queue_email(db, "ana@example.com", "A", "x", category="t", dedupe_key="k1") is None
        db.commit()
        assert queue_email(db, "ana@example.com", "A", "x", category="t", dedupe_key="k1") is None
        assert queue_email(db, None, "A", "x", category="t") is None
        assert queue_email(db, "sin-arroba", "A", "x", category="t") is None
        db.commit()
    assert len(statuses(sessions)) == 1


def test_provider_errors_are_retried_with_backoff_then_marked_failed(sessions):
    with sessions() as db:
        queue_email(db, "ana@example.com", "Hola", "x", category="test")
        db.commit()
        bind = db.get_bind()
    with patch.object(email_service, "send", side_effect=OSError("SMTP caído")):
        for attempt in range(1, email_service.MAX_ATTEMPTS + 1):
            with sessions() as db:
                item = db.query(EmailOutbox).one()
                item.next_attempt_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(1)
                db.commit()
            result = deliver_pending(bind)
            with sessions() as db:
                item = db.query(EmailOutbox).one()
                assert item.attempts == attempt
                assert "SMTP caído" in item.last_error
                if attempt < email_service.MAX_ATTEMPTS:
                    assert item.status == "pending"
                    assert item.next_attempt_at > datetime.now(UTC).replace(tzinfo=None)
    assert result == {"sent": 0, "failed": 1}
    assert statuses(sessions) == [("failed", email_service.MAX_ATTEMPTS)]


def test_smtp_backend_uses_starttls_and_login(sessions, monkeypatch):
    from app.db.database import settings

    monkeypatch.setattr(settings, "email_backend", "smtp")
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_username", "usuario")
    monkeypatch.setattr(settings, "smtp_password", "clave")
    with sessions() as db:
        queue_email(db, "ana@example.com", "Hola", "x", category="test")
        db.commit()
        bind = db.get_bind()
    with patch("smtplib.SMTP") as smtp:
        assert deliver_pending(bind)["sent"] == 1
    client = smtp.return_value.__enter__.return_value
    smtp.assert_called_once_with("smtp.example.com", 587, timeout=20)
    client.starttls.assert_called_once()
    client.login.assert_called_once_with("usuario", "clave")
    client.send_message.assert_called_once()


# Enlaces de un solo uso.


def test_tokens_are_single_use_expire_and_replace_older_ones(sessions):
    uid = user_id(sessions)
    with sessions() as db:
        first = issue_token(db, uid, "reset")
        second = issue_token(db, uid, "reset")
        db.commit()
        stored = [t.token_hash for t in db.query(OneTimeToken)]
    assert first not in stored and second not in stored  # only hashes are kept
    with sessions() as db:
        with pytest.raises(HTTPException):
            consume_token(db, first, ("reset",))  # replaced by the second
        with pytest.raises(HTTPException):
            consume_token(db, second, ("invite",))  # wrong purpose
        assert consume_token(db, second, ("reset",)).user_id == uid
        db.commit()
        with pytest.raises(HTTPException):
            consume_token(db, second, ("reset",))  # already used
        expired = issue_token(db, uid, "invite")
        db.query(OneTimeToken).filter_by(purpose="invite", used_at=None).update(
            {OneTimeToken.expires_at: datetime.now(UTC).replace(tzinfo=None) - timedelta(1)}
        )
        db.commit()
        with pytest.raises(HTTPException):
            consume_token(db, expired, ("invite",))
