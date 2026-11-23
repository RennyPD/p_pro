"""Which institution a request is addressed to, from its host (Fase 4 B).

``colegio-horizonte.nexo.do`` → the institution whose code is
``colegio-horizonte``; ``admin.nexo.do`` is the platform panel. Only hosts
under ``TENANT_BASE_DOMAIN`` are trusted; any other host (localhost, an IP, a
spoofed name) resolves to nothing and sign-in falls back to the institution
code.
"""

import re
from urllib.parse import urlsplit

from fastapi import Request
from sqlalchemy.orm import Session

from app.db.database import settings
from app.models.institution_model import Institution

RESERVED_CODES = frozenset(
    {
        "admin",
        "api",
        "app",
        "plataforma",
        "platform",
        "www",
        "mail",
        "soporte",
        "support",
        "static",
        "assets",
        "demo",
        "status",
    }
)
PLATFORM_LABEL = "admin"
CODE_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])$")


def host_label(host: str | None) -> str | None:
    """The first label of a host under the base domain, else None."""
    domain = (settings.tenant_base_domain or "").strip().lower()
    if not domain or not host:
        return None
    name = host.split(":", 1)[0].strip().lower().rstrip(".")
    suffix = "." + domain
    if not name.endswith(suffix):
        return None
    label = name[: -len(suffix)]
    return label if label and "." not in label else None


def request_label(request: Request | None) -> str | None:
    """Label of the address the request comes from.

    The ``Host`` when the API is served under the institution's own address;
    otherwise (API on ``api.<domain>``) the page's ``Origin``. Neither is a
    credential: tokens carry their institution and are checked against it.
    """
    if request is None:
        return None
    label = host_label(request.headers.get("host"))
    if label is not None and label not in RESERVED_CODES:
        return label
    origin = request.headers.get("origin") or ""
    origin_label = host_label(urlsplit(origin).hostname) if origin else None
    return origin_label if origin_label is not None else label


def institution_for_host(db: Session, request: Request | None) -> Institution | None:
    label = request_label(request)
    if label is None or label == PLATFORM_LABEL:
        return None
    return db.query(Institution).filter(Institution.slug == label).first()


def valid_code(code: str) -> bool:
    return bool(CODE_PATTERN.fullmatch(code)) and code not in RESERVED_CODES
