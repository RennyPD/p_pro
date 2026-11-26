"""Electronic fiscal receipts (e-CF) through an authorized provider (Fase 4, block F5).

Under Ley 32-23 the e-CF is signed (XML, digital certificate) and sent to the
DGII. An authorized provider does both: Nexo sends it the receipt and keeps
the answer (TrackId, security code, signing date and the QR link printed on
the receipt). Changing provider means writing another adapter.

- ``SandboxEcfProvider``: accepts at once with a test security code (never in
  production).
- A real provider is added here once the institutions choose one.

Sending never blocks a payment: the receipt waits as ``pending`` and the worker
sends it again every 10 minutes.
"""

import hashlib
import hmac
import urllib.parse
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException

from app.db.database import settings


@dataclass(frozen=True)
class EcfResult:
    status: str  # accepted | in_process | rejected
    track_id: str | None = None
    security_code: str | None = None
    signed_at: datetime | None = None
    qr_url: str | None = None
    message: str | None = None


def timbre_url(base: str, document, issuer_rnc: str, signed_at: datetime, code: str) -> str:
    """The DGII's receipt check link printed as a QR code."""
    query = {
        "RncEmisor": issuer_rnc,
        "RncComprador": document.buyer_tax_id or "",
        "ENCF": document.ncf,
        "FechaEmision": document.issued_at.strftime("%d-%m-%Y"),
        "MontoTotal": f"{document.total:.2f}",
        "FechaFirma": signed_at.strftime("%d-%m-%Y %H:%M:%S"),
        "CodigoSeguridad": code,
    }
    return f"{base}?{urllib.parse.urlencode(query)}"


class SandboxEcfProvider:
    name = "sandbox"
    TIMBRE = "https://ecf.dgii.gov.do/testecf/ConsultaTimbre"

    @property
    def enabled(self) -> bool:
        return settings.app_environment != "production"

    def submit(self, document, profile, secrets) -> EcfResult:
        if not self.enabled:
            raise HTTPException(
                503, "El proveedor de e-CF de prueba no está disponible en producción"
            )
        signed_at = datetime.now(UTC).replace(tzinfo=None)
        digest = hmac.new(
            settings.secret_key.encode(), document.ncf.encode(), hashlib.sha256
        ).hexdigest()
        code = digest[:6].upper()
        return EcfResult(
            status="accepted",
            track_id=f"SBX-{digest[6:22]}",
            security_code=code,
            signed_at=signed_at,
            qr_url=timbre_url(self.TIMBRE, document, profile.rnc, signed_at, code),
            message="Aceptado (prueba)",
        )

    def status(self, document, profile, secrets) -> EcfResult | None:
        return None


PROVIDERS = {"sandbox": SandboxEcfProvider}


def provider_for(name: str):
    try:
        return PROVIDERS[name]()
    except KeyError as exc:
        raise HTTPException(409, "El proveedor de e-CF configurado no existe") from exc
