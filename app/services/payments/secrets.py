"""Encryption of each institution's gateway credentials (Fase 4, block E).

Fernet (AES-128-CBC + HMAC-SHA256) with keys from PAYMENTS_ENCRYPTION_KEY.
Several keys separated by commas allow rotation: the first encrypts, all of
them decrypt. Secrets never go back to the browser.
"""

import json

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from fastapi import HTTPException

from app.db.database import settings

MISSING = (
    "Falta configurar la clave de cifrado de los pagos en línea (PAYMENTS_ENCRYPTION_KEY). "
    "Escribe al equipo de Nexo"
)


def _cipher() -> MultiFernet:
    keys = [
        key.strip() for key in (settings.payments_encryption_key or "").split(",") if key.strip()
    ]
    if not keys:
        raise HTTPException(503, MISSING)
    try:
        return MultiFernet([Fernet(key.encode()) for key in keys])
    except ValueError as exc:
        raise HTTPException(503, MISSING) from exc


def encrypt(values: dict[str, str]) -> str:
    return _cipher().encrypt(json.dumps(values, sort_keys=True).encode()).decode()


def decrypt(token: str) -> dict[str, str]:
    if not token:
        return {}
    try:
        return json.loads(_cipher().decrypt(token.encode()).decode())
    except InvalidToken as exc:
        raise HTTPException(
            503, "No se pudieron leer las credenciales de la pasarela. Vuelve a guardarlas"
        ) from exc


def mask(value: str | None) -> str:
    """For the screen: only the last 4 characters."""
    if not value:
        return ""
    return "•" * max(0, min(len(value) - 4, 8)) + value[-4:]
