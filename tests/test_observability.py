"""Error tracking without personal data and readiness checks (Fase 4 C)."""

import sentry_sdk
from fastapi.testclient import TestClient
from sentry_sdk.transport import Transport

from app import observability
from app.db.database import settings
from app.services import storage
from main import app


def test_scrub_keeps_the_error_and_drops_personal_data():
    event = {
        "request": {
            "method": "POST",
            "url": "https://colegio.nexo.do/students/5?q=ana",
            "data": {"first_name": "Ana"},
            "headers": {"Authorization": "Bearer abc"},
            "cookies": {"nexo_refresh": "x"},
            "query_string": "q=ana",
        },
        "user": {"id": 5, "email": "ana@correo.do"},
        "breadcrumbs": {"values": [{"message": "SELECT * FROM students"}]},
        "extra": {"payload": "secreto"},
        "contexts": {"runtime": {"name": "CPython"}, "custom": {"cedula": "00112345678"}},
        "message": "Fallo con ana@correo.do y cédula 001-1234567-8",
        "exception": {
            "values": [
                {
                    "value": "duplicate key (email)=(ana@correo.do) token=abc123",
                    "stacktrace": {"frames": [{"function": "f", "vars": {"password": "x"}}]},
                }
            ]
        },
        "tags": {"institution_id": "2", "request_id": "r1", "email": "ana@correo.do"},
    }
    clean = observability.scrub(event)
    assert clean["request"] == {"method": "POST", "url": "https://colegio.nexo.do/students/5"}
    assert "user" not in clean and "breadcrumbs" not in clean and "extra" not in clean
    assert clean["contexts"] == {"runtime": {"name": "CPython"}}
    assert clean["message"] == "Fallo con [correo] y cédula [número]"
    value = clean["exception"]["values"][0]["value"]
    assert "ana@correo.do" not in value and "abc123" not in value
    assert "vars" not in clean["exception"]["values"][0]["stacktrace"]["frames"][0]
    assert clean["tags"] == {"institution_id": "2", "request_id": "r1"}


def test_sentry_is_off_without_a_dsn(monkeypatch):
    monkeypatch.setattr(settings, "sentry_dsn", None)
    called = []
    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: called.append(kwargs))
    assert observability.init_sentry() is False and called == []
    observability.tag("institution_id", 1)  # harmless when disabled


def test_events_reach_sentry_already_scrubbed(monkeypatch):
    sent = []

    class Capture(Transport):
        def capture_envelope(self, envelope):
            sent.extend(item.payload.json for item in envelope.items if item.payload.json)

    real_init = sentry_sdk.init
    monkeypatch.setattr(settings, "sentry_dsn", "https://clave@errores.example/1")
    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: real_init(transport=Capture, **kwargs))
    try:
        assert observability.init_sentry() is True
        options = sentry_sdk.get_client().options
        assert not options.get("send_default_pii") and options["max_request_body_size"] == "never"
        observability.tag("institution_id", 3)
        try:
            raise ValueError("No se pudo guardar a ana@correo.do (809-555-1234)")
        except ValueError as error:
            sentry_sdk.capture_exception(error)
        sentry_sdk.flush()
    finally:
        sentry_sdk.get_client().close()
        sentry_sdk.init()  # back to a disabled client for the other tests
    events = [event for event in sent if event.get("exception")]
    assert len(events) == 1
    value = events[0]["exception"]["values"][0]["value"]
    assert value == "No se pudo guardar a [correo] ([número])"
    assert events[0]["tags"]["institution_id"] == "3"
    assert "user" not in events[0]


def test_ready_checks_database_and_storage(monkeypatch):
    with TestClient(app) as client:
        ok = client.get("/health/ready")
        assert ok.status_code == 200
        assert ok.json() == {"status": "ok", "checks": {"database": "ok", "storage": "ok"}}

        def broken(_self):
            raise storage.StorageError("credenciales inválidas para el bucket")

        monkeypatch.setattr(storage.LocalStorage, "check", broken)
        down = client.get("/health/ready")
    assert down.status_code == 503
    assert down.json() == {
        "status": "unavailable",
        "checks": {"database": "ok", "storage": "error"},
    }
    assert "credenciales" not in down.text
