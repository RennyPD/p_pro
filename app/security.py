import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status

from app.db.database import settings


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt_text, digest_text = encoded.split("$", 2)
        if algorithm != "scrypt":
            return False
        salt = base64.urlsafe_b64decode(salt_text)
        expected = base64.urlsafe_b64decode(digest_text)
        actual = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _encode_part(value: dict) -> str:
    raw = json.dumps(value, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _decode_part(value: str) -> dict:
    padded = value + "=" * (-len(value) % 4)
    return json.loads(base64.urlsafe_b64decode(padded))


def create_access_token(user_id: int) -> str:
    now = int(time.time())
    header = _encode_part({"alg": "HS256", "typ": "JWT"})
    payload = _encode_part(
        {
            "sub": str(user_id),
            "iat": now,
            "exp": now + settings.access_token_expire_minutes * 60,
        }
    )
    message = f"{header}.{payload}".encode()
    signature = (
        base64.urlsafe_b64encode(
            hmac.new(settings.secret_key.encode(), message, hashlib.sha256).digest()
        )
        .rstrip(b"=")
        .decode()
    )
    return f"{header}.{payload}.{signature}"


def decode_access_token(token: str) -> int:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired access token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        header, payload, signature = token.split(".")
        message = f"{header}.{payload}".encode()
        expected = (
            base64.urlsafe_b64encode(
                hmac.new(settings.secret_key.encode(), message, hashlib.sha256).digest()
            )
            .rstrip(b"=")
            .decode()
        )
        if not hmac.compare_digest(signature, expected):
            raise credentials_error
        claims = _decode_part(payload)
        if int(claims["exp"]) < int(time.time()):
            raise credentials_error
        return int(claims["sub"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise credentials_error


def create_refresh_token() -> tuple[str, str, datetime]:
    token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(
        days=settings.refresh_token_expire_days
    )
    return token, token_hash, expires_at


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
