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


# Paso 2: recuperación de contraseña e invitaciones (de punta a punta).

import re  # noqa: E402

from test_write_audit import demo, entries  # noqa: E402, F401  (shared fixture)


@pytest.fixture
def mailer(demo, monkeypatch):  # noqa: F811
    from app.db.database import settings

    monkeypatch.setattr(settings, "app_url", "https://nexo.example.edu")
    return demo


def last_email(sessions, to):
    with sessions() as db:
        item = (
            db.query(EmailOutbox)
            .filter_by(to_address=to)
            .order_by(EmailOutbox.email_id.desc())
            .first()
        )
        return item and (item.subject, item.body_text, item.status, item.category)


def link_token(body):
    return re.search(r"token=([A-Za-z0-9_\-]+)", body).group(1)


def login(client, username, password):
    return client.post("/auth/login", json={"username": username, "password": password})


def test_password_reset_by_email_end_to_end(mailer):
    client, sessions, tokens = mailer
    with sessions() as db:
        admin = db.query(User).filter_by(username="demo.admin").one()
        address = admin.email
    answer = client.post("/auth/password-reset/request", json={"identifier": "DEMO.ADMIN"})
    assert answer.status_code == 202
    subject, body, status, category = last_email(sessions, address)
    assert "Restablece tu contraseña" in subject and category == "security"
    assert status == "sent"  # delivered after the response (console backend)
    assert "https://nexo.example.edu/restablecer?token=" in body
    token = link_token(body)

    weak = client.post(
        "/auth/password-reset/confirm", json={"token": token, "new_password": "corta"}
    )
    assert weak.status_code == 422
    done = client.post(
        "/auth/password-reset/confirm",
        json={"token": token, "new_password": "Una-clave-nueva-2026"},
    )
    assert done.status_code == 204, done.text
    assert client.get("/auth/me", headers=tokens["admin"]).status_code == 401  # sessions closed
    assert login(client, "demo.admin", "Una-clave-nueva-2026").status_code == 200
    again = client.post(
        "/auth/password-reset/confirm",
        json={"token": token, "new_password": "Otra-clave-nueva-2026"},
    )
    assert again.status_code == 400
    with sessions() as db:
        from app.models.security_model import AuditLog

        actions = {a.action for a in db.query(AuditLog).filter_by(user_id=admin.user_id)}
    assert {"password.reset.requested", "password.reset.completed"} <= actions


def test_reset_answer_does_not_reveal_accounts_and_is_rate_limited(mailer):
    client, sessions, _ = mailer
    unknown = client.post("/auth/password-reset/request", json={"identifier": "nadie@example.com"})
    assert unknown.status_code == 202
    known = client.post("/auth/password-reset/request", json={"identifier": "demo.docente"})
    assert unknown.json() == known.json()
    with sessions() as db:
        assert db.query(EmailOutbox).count() == 1
    for _ in range(4):
        client.post("/auth/password-reset/request", json={"identifier": "nadie@example.com"})
    blocked = client.post("/auth/password-reset/request", json={"identifier": "nadie@example.com"})
    assert blocked.status_code == 429
    # Sign-in for the same name keeps its own counter.
    assert login(client, "demo.docente", "NexoDocente2026!").status_code == 200


def test_reset_without_app_url_fails_the_same_for_every_account(demo):  # noqa: F811
    client, _, _ = demo
    for identifier in ("demo.admin", "nadie"):
        response = client.post("/auth/password-reset/request", json={"identifier": identifier})
        assert response.status_code == 503


def test_invited_account_activates_from_the_email(mailer):
    client, sessions, tokens = mailer
    with sessions() as db:
        role = db.query(Role).filter_by(name="teacher").first() or db.query(Role).first()
        role_id = role.role_id
    missing = client.post(
        "/users/",
        headers=tokens["admin"],
        json={"username": "invitada", "email": "invitada@example.com", "role_id": role_id},
    )
    assert missing.status_code == 422
    created = client.post(
        "/users/",
        headers=tokens["admin"],
        json={
            "username": "invitada",
            "email": "invitada@example.com",
            "role_id": role_id,
            "invite": True,
        },
    )
    assert created.status_code == 200, created.text
    user = created.json()["user_id"]
    subject, body, status, _ = last_email(sessions, "invitada@example.com")
    assert "Activa tu cuenta" in subject and "«invitada»" in body and status == "sent"
    first = link_token(body)

    resent = client.post(f"/users/{user}/invitation", headers=tokens["admin"])
    assert resent.status_code == 202, resent.text
    second = link_token(last_email(sessions, "invitada@example.com")[1])
    assert first != second
    stale = client.post(
        "/auth/password-reset/confirm", json={"token": first, "new_password": "Clave-invitada-2026"}
    )
    assert stale.status_code == 400
    activated = client.post(
        "/auth/password-reset/confirm",
        json={"token": second, "new_password": "Clave-invitada-2026"},
    )
    assert activated.status_code == 204, activated.text
    assert login(client, "invitada", "Clave-invitada-2026").status_code == 200
    assert entries(sessions, "user.invitation.sent")[0][0] == "demo.admin"
    assert client.post(f"/users/{user}/invitation", headers=tokens["docente"]).status_code == 403


# Paso 3: avisos por correo y preferencias.

from test_guardian_links import family  # noqa: E402, F401
from test_payments_module import add_charges  # noqa: E402


def emails(sessions, category):
    with sessions() as db:
        return sorted(
            (e.to_address, e.status) for e in db.query(EmailOutbox).filter_by(category=category)
        )


def address(sessions, username):
    with sessions() as db:
        return db.query(User).filter_by(username=username).one().email


def test_preferences_are_read_and_saved_with_audit(demo):  # noqa: F811
    client, sessions, tokens = demo
    headers = tokens["estudiante"]
    assert client.get("/auth/email-preferences", headers=headers).json() == {
        "email_announcements": True,
        "email_grades": True,
        "email_due_reminders": True,
    }
    saved = client.put(
        "/auth/email-preferences",
        headers=headers,
        json={"email_announcements": False, "email_grades": True, "email_due_reminders": True},
    )
    assert saved.status_code == 200 and saved.json()["email_announcements"] is False
    with sessions() as db:
        from app.models.security_model import AuditLog

        entry = db.query(AuditLog).filter_by(action="email.preferences.updated").one()
    assert "email_announcements: no" in entry.detail


def test_announcements_reach_recipients_who_accept_them(demo):  # noqa: F811
    client, sessions, tokens = demo
    student = address(sessions, "demo.estudiante")
    published = client.post(
        "/community/announcements",
        headers=tokens["admin"],
        json={
            "title": "Feria científica",
            "body": "El viernes no hay clases.",
            "audience": "student",
        },
    )
    assert published.status_code == 200, published.text
    assert (student, "sent") in emails(sessions, "announcement")  # no APP_URL needed

    client.put(
        "/auth/email-preferences",
        headers=tokens["estudiante"],
        json={"email_announcements": False, "email_grades": True, "email_due_reminders": True},
    )
    again = client.post(
        "/community/announcements",
        headers=tokens["admin"],
        json={"title": "Simulacro", "body": "Simulacro de evacuación.", "audience": "student"},
    )
    assert again.status_code == 200
    assert [e for e in emails(sessions, "announcement") if e[0] == student] == [(student, "sent")]


def test_published_grades_reach_the_student_and_guardians_allowed_to_see_them(family):  # noqa: F811
    from app.models import Assessment, Enrollment, Grade
    from app.services.business_time import business_date

    client, sessions, tokens, tutor, link_id, student_id = family
    with sessions() as db:
        enrollment = (
            db.query(Enrollment)
            .filter_by(student_id=student_id, state="enrolled")
            .order_by(Enrollment.enrollment_id)
            .first()
        )
        assessment = Assessment(
            section_id=enrollment.section_id, name="Quiz de correo", weight=5, closed=False
        )
        db.add(assessment)
        db.flush()
        db.add(
            Grade(
                enrollment_id=enrollment.enrollment_id,
                assessment_id=assessment.assessment_id,
                grade_value=91,
                grade_type="Quiz de correo",
                date_recorded=business_date(),
                status="draft",
            )
        )
        db.commit()
        assessment_id = assessment.assessment_id
        own = db.query(User).filter_by(student_id=student_id).first()
        tutor_email = db.query(User).filter_by(username="tutor.01").one().email
    client.patch(
        f"/community/guardian-links/{link_id}",
        headers=tokens["admin"],
        json={"can_view_academic": False},
    )
    published = client.post(f"/grades/assessments/{assessment_id}/publish", headers=tokens["admin"])
    assert published.status_code == 200, published.text
    recipients = [e[0] for e in emails(sessions, "grades")]
    assert tutor_email not in recipients  # link without access to grades
    assert own is not None and own.email in recipients


def test_due_reminders_go_once_before_and_after_and_respect_access(family):  # noqa: F811
    from datetime import timedelta

    from app.models import InstitutionSettings
    from app.services.business_time import business_date
    from app.services.email_notices import queue_due_reminders

    client, sessions, tokens, tutor, link_id, student_id = family
    add_charges(sessions, student_id, ("300.00", 2), ("200.00", -1), ("100.00", 20))
    tutor_email = address(sessions, "tutor.01")
    with sessions() as db:
        first = queue_due_reminders(db, business_date())
        db.commit()
        second = queue_due_reminders(db, business_date())
        db.commit()
        rows = db.query(EmailOutbox).filter_by(category="due_reminder", to_address=tutor_email)
        subjects = sorted(e.subject.split(" · ")[0] for e in rows)
    assert first >= 2 and second == 0  # never repeated
    assert subjects == ["Pago próximo a vencer", "Pago vencido"]

    with sessions() as db:
        settings = db.get(InstitutionSettings, 1) or InstitutionSettings(settings_id=1)
        settings.students_view_finance = False
        db.merge(settings)
        db.commit()
    client.patch(
        f"/community/guardian-links/{link_id}",
        headers=tokens["admin"],
        json={"can_view_finance": False},
    )
    add_charges(sessions, student_id, ("50.00", 3))
    with sessions() as db:
        assert queue_due_reminders(db, business_date() + timedelta(days=0)) == 0
