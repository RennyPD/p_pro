"""The interface's address for links that leave Nexo and come back (payments)."""

import re

from fastapi import HTTPException, Request

from app.db.database import settings


def frontend_base(request: Request) -> str:
    """The page that asked, if it is one of ours (CORS origins); else APP_URL."""
    origin = (request.headers.get("origin") or "").rstrip("/")
    allowed = {item.strip().rstrip("/") for item in settings.cors_origins.split(",")}
    trusted = origin in allowed or bool(
        settings.cors_origin_regex and re.fullmatch(settings.cors_origin_regex, origin)
    )
    base = origin if origin and trusted else (settings.app_url or "").rstrip("/")
    if not base:
        raise HTTPException(503, "Falta configurar la dirección de la aplicación (APP_URL)")
    return base
