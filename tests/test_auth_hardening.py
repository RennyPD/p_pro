"""Audit low findings: single-use TOTP, refresh token reuse, protected bootstrap."""

import time
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from test_account_access import PASSWORDS, context, headers, login  # noqa: F401

from app.db.database import settings
from app.models import User
from app.models.security_model import AuditLog, RefreshToken
from app.security import create_totp_secret, totp_step


def current_code(secret: str) -> str:
    # RFC 6238 code for the current 30-second step.
    import base64
    import hashlib
    import hmac

    key = base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)
    digest = hmac.new(key, (int(time.time()) // 30).to_bytes(8, "big"), hashlib.sha1).digest()
    index = digest[-1] & 15
    return f"{(int.from_bytes(digest[index : index + 4], 'big') & 0x7FFFFFFF) % 1_000_000:06d}"


def test_totp_step_identifies_the_window():
    secret = create_totp_secret()
    assert totp_step(secret, current_code(secret)) == int(time.time()) // 30
    assert totp_step(secret, "abcdef") is None


def test_totp_code_is_accepted_only_once(context):  # noqa: F811
    client, sessions = context
    secret = create_totp_secret()
    with sessions() as db:
        user = db.query(User).filter_by(username="demo.docente").one()
        user.mfa_secret, user.mfa_enabled = secret, True
        db.commit()
    code = current_code(secret)
    payload = {"username": "demo.docente", "password": PASSWORDS["demo.docente"], "otp": code}
    assert client.post("/auth/login", json=payload).status_code == 200
    replay = client.post("/auth/login", json=payload)
    assert replay.status_code == 401


def test_reused_rotated_refresh_token_revokes_every_session(context):  # noqa: F811
    client, sessions = context
    token = headers(client, "demo.docente")
    stolen = client.cookies.get("refresh_token")
    assert client.post("/auth/refresh").status_code == 200  # legitimate rotation
    with sessions() as db:
        rotated = db.query(RefreshToken).filter(RefreshToken.rotated_at.isnot(None)).one()
        rotated.rotated_at -= timedelta(minutes=5)  # outside the parallel-tab grace
        db.commit()
    client.cookies.clear()
    reuse = client.post("/auth/refresh", headers={"Cookie": f"refresh_token={stolen}"})
    assert reuse.status_code == 401
    assert "uso repetido" in reuse.json()["detail"]
    assert client.get("/auth/me", headers=token).status_code == 401
    with sessions() as db:
        assert db.query(AuditLog).filter_by(action="session.reuse_detected").count() == 1
        assert db.query(RefreshToken).filter(RefreshToken.revoked_at.is_(None)).count() == 0


def test_logged_out_token_does_not_raise_a_theft_alarm(context):  # noqa: F811
    client, sessions = context
    headers(client, "demo.docente")
    old = client.cookies.get("refresh_token")
    client.post("/auth/logout")
    fresh = headers(client, "demo.docente")
    with sessions() as db:
        for row in db.query(RefreshToken).filter(RefreshToken.revoked_at.isnot(None)):
            row.revoked_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=5)
        db.commit()
    stale = client.post("/auth/refresh", headers={"Cookie": f"refresh_token={old}"})
    assert stale.status_code == 401
    assert client.get("/auth/me", headers=fresh).status_code == 200


@pytest.mark.parametrize(
    ("environment", "token", "sent", "expected"),
    [
        ("production", None, None, 403),
        ("production", "s3creto-de-instalacion", "otro", 403),
        ("development", "s3creto-de-instalacion", None, 403),
        # Valid token: the guard lets it through and the existing users answer 409.
        ("production", "s3creto-de-instalacion", "s3creto-de-instalacion", 409),
    ],
)
def test_bootstrap_requires_the_configured_token(context, environment, token, sent, expected):  # noqa: F811
    client, _ = context
    request_headers = {"X-Bootstrap-Token": sent} if sent else {}
    with (
        patch.object(settings, "app_environment", environment),
        patch.object(settings, "bootstrap_token", token),
    ):
        response = client.post(
            "/auth/bootstrap",
            json={"username": "nuevo", "email": "nuevo@example.com", "password": "Clave2026!!"},
            headers=request_headers,
        )
    assert response.status_code == expected
