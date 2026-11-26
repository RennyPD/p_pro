"""Request limits on uploads, exports, imports and public routes (Fase 4 C, audit B7)."""

import re
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute
from sqlalchemy import func
from test_route_permissions import routes
from test_write_audit import demo  # noqa: F401  (shared fixture)

from app.db.database import settings
from app.models import RateLimit
from app.services import rate_limit
from app.services.rate_limit import Limit, hit, purge

SMALL = Limit("prueba", 3, 600, "Demasiadas peticiones de prueba")
MOMENT = datetime(2026, 11, 25, 10, 1, 0)


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch):
    """Route tests make many requests: they must not straddle two windows."""
    monkeypatch.setattr(rate_limit, "now", lambda: MOMENT)


def test_counts_per_window_and_answers_429_with_retry_after(demo):  # noqa: F811
    _client, sessions, _tokens = demo
    with sessions() as db:
        for _ in range(3):
            hit(db, SMALL, "1:7", MOMENT)
        with pytest.raises(HTTPException) as blocked:
            hit(db, SMALL, "1:7", MOMENT)
        assert blocked.value.status_code == 429
        assert blocked.value.detail == "Demasiadas peticiones de prueba"
        # The window started at 10:00 and lasts 10 minutes: 9 minutes to go.
        assert blocked.value.headers["Retry-After"] == "540"
        # Other accounts and other institutions keep their own count.
        hit(db, SMALL, "1:8", MOMENT)
        hit(db, SMALL, "2:7", MOMENT)
        # A new window starts from zero.
        hit(db, SMALL, "1:7", MOMENT + timedelta(minutes=10))


def test_a_failed_request_still_counts(demo):  # noqa: F811
    _client, sessions, _tokens = demo
    with sessions() as db:
        hit(db, SMALL, "1:9", MOMENT)
        db.rollback()  # the request's own transaction fails
    with sessions() as db:
        assert db.get(RateLimit, "prueba:1:9").hits == 1


def test_limits_can_be_switched_off(demo, monkeypatch):  # noqa: F811
    _client, sessions, _tokens = demo
    monkeypatch.setattr(settings, "rate_limits_enabled", False)
    with sessions() as db:
        for _ in range(5):
            hit(db, SMALL, "1:10", MOMENT)
        assert db.query(func.count()).select_from(RateLimit).scalar() == 0


def test_public_lookup_is_limited_per_address(demo):  # noqa: F811
    client, _sessions, _tokens = demo
    for _ in range(rate_limit.PUBLIC.hits):
        assert client.get("/public/institution?code=principal").status_code == 200
    blocked = client.get("/public/institution?code=principal")
    assert blocked.status_code == 429
    assert "Espera" in blocked.json()["detail"] and int(blocked.headers["Retry-After"]) >= 1


def test_platform_sign_in_is_limited(demo):  # noqa: F811
    client, _sessions, _tokens = demo
    body = {"email": "nadie@nexo.com.do", "password": "ContraseñaFalsa1", "otp": "000000"}
    codes = [
        client.post("/platform/auth/login", json=body).status_code
        for _ in range(rate_limit.PLATFORM_LOGIN.hits + 1)
    ]
    assert codes[:-1] == [401] * rate_limit.PLATFORM_LOGIN.hits and codes[-1] == 429


def test_exports_are_limited_per_account(demo):  # noqa: F811
    client, _sessions, tokens = demo
    url = "/bulk/students/export"
    for _ in range(rate_limit.EXPORTS.hits):
        assert client.get(url, headers=tokens["admin"]).status_code == 200
    assert client.get(url, headers=tokens["admin"]).status_code == 429


def test_purge_forgets_old_windows(demo):  # noqa: F811
    _client, sessions, _tokens = demo
    with sessions() as db:
        hit(db, SMALL, "1:11", datetime(2020, 1, 1))
        hit(db, SMALL, "1:12")
        assert purge(db.get_bind()) == 1
        assert [row.rate_key for row in db.query(RateLimit)] == ["prueba:1:12"]


# Routes that send files, generate documents or accept uploads and imports.
HEAVY = re.compile(r"\.(pdf|csv|txt)$|/export$|/import$|/download$|/attachment$|/proof$")
UPLOADS = {
    ("POST", "/operations/students/{student_id}/documents"),
    ("POST", "/assignments/{assignment_id}/submit"),
    ("POST", "/finance/students/{student_id}/transfers"),
    ("POST", "/guardian/transfers"),
}
PUBLIC = {
    ("GET", "/public/institution"),
    ("POST", "/platform/auth/login"),
    ("POST", "/public/signup"),
}


def limited(route: APIRoute) -> bool:
    return any(hasattr(item.call, "rate_limit") for item in route.dependant.dependencies)


def test_every_heavy_route_declares_a_limit():
    missing, checked = [], 0
    for method, path, route in routes():
        heavy = (method == "GET" and HEAVY.search(path)) or (method, path) in UPLOADS | PUBLIC
        if not heavy:
            continue
        checked += 1
        if not limited(route):
            missing.append(f"{method} {path}")
    assert checked >= 20, checked
    assert missing == [], "Rutas sin límite de peticiones:\n" + "\n".join(missing)
