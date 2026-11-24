"""Card payment gateways of the institutions (Fase 4, block E2).

All of them use the bank's hosted payment page: card data never reaches Nexo
(PCI SAQ-A). Each adapter knows how to send the payer there and how to verify
the answer:

- ``SandboxGateway``: a test page inside Nexo (never in production).
- ``AzulGateway``: «Página de Pagos» of Azul (Banco Popular). The request and
  the answer are signed with HMAC-SHA512 and the merchant's AuthKey.
- ``CardnetGateway``: CardNet's payment button. A session is created server
  to server and the result is read back server to server.

The Azul and CardNet adapters follow the banks' published integration guides;
each bank certifies the integration with the institution's test credentials
before going live (see docs/pagos-en-linea.md).
"""

import hashlib
import hmac
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from fastapi import HTTPException

from app.db.database import settings

UNREACHABLE = "No se pudo contactar al banco. Intenta de nuevo en unos minutos"


@dataclass(frozen=True)
class Redirect:
    """Where the payer's browser goes: a GET link or a self-submitting POST form."""

    method: str
    url: str
    fields: dict


@dataclass(frozen=True)
class GatewayResult:
    status: str  # approved | declined | error
    amount_cents: int | None = None
    authorization_code: str | None = None
    provider_reference: str | None = None
    response_code: str | None = None
    message: str | None = None


def cents_text(cents: int) -> str:
    return str(int(cents))


class SandboxGateway:
    name = "sandbox"

    @property
    def enabled(self) -> bool:
        return settings.app_environment != "production"

    def start(self, intent, config, secrets, return_url: str) -> Redirect:
        if not self.enabled:
            raise HTTPException(503, "La pasarela de prueba no está disponible en producción")
        return Redirect("GET", f"{return_url}/sandbox", {"id": intent.public_id})

    def verify(self, params: dict, intent, config, secrets) -> GatewayResult:
        if not self.enabled:
            raise HTTPException(400, "La pasarela de prueba no está disponible en producción")
        approved = params.get("outcome") == "approved"
        return GatewayResult(
            status="approved" if approved else "declined",
            amount_cents=int(round(float(intent.amount) * 100)),
            authorization_code="SBX123" if approved else None,
            provider_reference=f"SBX-{intent.public_id[:12]}",
            response_code="00" if approved else "51",
            message="Aprobada (prueba)" if approved else "Rechazada (prueba)",
        )

    def query(self, intent, config, secrets) -> GatewayResult | None:
        return None


class AzulGateway:
    name = "azul"
    enabled = True
    TEST_URL = "https://pruebas.azul.com.do/PaymentPage/"
    LIVE_URL = "https://pagos.azul.com.do/PaymentPage/"
    REQUEST_FIELDS = (
        "MerchantId", "MerchantName", "MerchantType", "CurrencyCode", "OrderNumber", "Amount",
        "ITBIS", "ApprovedUrl", "DeclinedUrl", "CancelUrl", "UseCustomField1",
        "CustomField1Label", "CustomField1Value", "UseCustomField2", "CustomField2Label",
        "CustomField2Value",
    )  # fmt: skip
    RESPONSE_FIELDS = (
        "OrderNumber", "Amount", "AuthorizationCode", "DateTime", "ResponseCode", "IsoCode",
        "ResponseMessage", "ErrorDescription", "RRN",
    )  # fmt: skip

    @staticmethod
    def signature(values: list[str], auth_key: str) -> str:
        message = "".join(values) + auth_key
        return hmac.new(auth_key.encode(), message.encode(), hashlib.sha512).hexdigest()

    def start(self, intent, config, secrets, return_url: str) -> Redirect:
        auth_key = secrets.get("auth_key")
        if not auth_key or not config.merchant_id:
            raise HTTPException(409, "Falta configurar el comercio de Azul de la institución")
        back = f"{return_url}/resultado?id={intent.public_id}"
        fields = {
            "MerchantId": config.merchant_id,
            "MerchantName": config.merchant_name[:40],
            "MerchantType": secrets.get("merchant_type", "E-Commerce"),
            "CurrencyCode": "$",
            "OrderNumber": intent.public_id[:15],
            "Amount": cents_text(int(round(float(intent.amount) * 100))),
            "ITBIS": "000",
            "ApprovedUrl": back,
            "DeclinedUrl": back,
            "CancelUrl": f"{back}&cancelado=1",
            "UseCustomField1": "0",
            "CustomField1Label": "",
            "CustomField1Value": "",
            "UseCustomField2": "0",
            "CustomField2Label": "",
            "CustomField2Value": "",
        }
        fields["AuthHash"] = self.signature([fields[k] for k in self.REQUEST_FIELDS], auth_key)
        url = self.TEST_URL if secrets.get("environment", "test") == "test" else self.LIVE_URL
        return Redirect("POST", url, fields)

    def verify(self, params: dict, intent, config, secrets) -> GatewayResult:
        if params.get("cancelado"):
            return GatewayResult(status="declined", message="Pago cancelado por la persona")
        auth_key = secrets.get("auth_key", "")
        values = [str(params.get(field, "")) for field in self.RESPONSE_FIELDS]
        expected = self.signature(values, auth_key)
        if not hmac.compare_digest(expected, str(params.get("AuthHash", "")).lower()):
            raise HTTPException(400, "La respuesta del banco no tiene una firma válida")
        if params.get("OrderNumber") != intent.public_id[:15]:
            raise HTTPException(400, "La respuesta del banco no corresponde a este pago")
        approved = params.get("IsoCode") == "00"  # ISO 8583 «approved»
        return GatewayResult(
            status="approved" if approved else "declined",
            amount_cents=int(params.get("Amount") or 0),
            authorization_code=params.get("AuthorizationCode") or None,
            provider_reference=params.get("AzulOrderId") or params.get("RRN") or None,
            response_code=params.get("IsoCode") or None,
            message=params.get("ResponseMessage") or params.get("ErrorDescription") or None,
        )

    def query(self, intent, config, secrets) -> GatewayResult | None:
        return None  # resolved by the institution with the bank's portal (block E5)


class CardnetGateway:
    name = "cardnet"
    enabled = True
    TEST_URL = "https://lab.cardnet.com.do"
    LIVE_URL = "https://ecommerce.cardnet.com.do"

    def __init__(self, opener=None):
        self.opener = opener or urllib.request.urlopen

    def base(self, secrets) -> str:
        return self.TEST_URL if secrets.get("environment", "test") == "test" else self.LIVE_URL

    def call(self, method: str, url: str, data: dict | None = None) -> dict:
        body = json.dumps(data).encode() if data is not None else None
        request = urllib.request.Request(url, data=body, method=method)
        request.add_header("Content-Type", "application/json")
        request.add_header("Accept", "application/json")
        try:
            with self.opener(request, timeout=20) as response:
                return json.loads(response.read().decode())
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            raise HTTPException(503, UNREACHABLE) from exc

    def start(self, intent, config, secrets, return_url: str) -> Redirect:
        terminal = secrets.get("terminal")
        if not terminal or not config.merchant_id:
            raise HTTPException(409, "Falta configurar el comercio de CardNet de la institución")
        back = f"{return_url}/resultado?id={intent.public_id}"
        session = self.call(
            "POST",
            f"{self.base(secrets)}/sessions",
            {
                "TransactionType": "200",
                "CurrencyCode": "214",
                "AcquiringInstitutionCode": "349",
                "MerchantType": secrets.get("merchant_type", "7997"),
                "MerchantNumber": config.merchant_id,
                "MerchantTerminal": terminal,
                "ReturnUrl": back,
                "CancelUrl": f"{back}&cancelado=1",
                "PageLanguaje": "ESP",
                "OrdenId": intent.public_id[:20],
                "TransactionId": str(intent.online_payment_id).zfill(6)[-6:],
                "Tax": "0",
                "MerchantName": config.merchant_name[:40],
                "Amount": cents_text(int(round(float(intent.amount) * 100))),
            },
        )
        if not session.get("SESSION") or not session.get("session-key"):
            raise HTTPException(502, "El banco no abrió la sesión de pago. Intenta de nuevo")
        # The session key is needed to read the result; kept with the intent.
        intent.provider_reference = f"{session['SESSION']}:{session['session-key']}"
        return Redirect("POST", f"{self.base(secrets)}/authorize", {"SESSION": session["SESSION"]})

    def verify(self, params: dict, intent, config, secrets) -> GatewayResult:
        if params.get("cancelado"):
            return GatewayResult(status="declined", message="Pago cancelado por la persona")
        result = self.query(intent, config, secrets)
        if result is None:
            raise HTTPException(400, "No se encontró la sesión de pago de este cobro")
        return result

    def query(self, intent, config, secrets) -> GatewayResult | None:
        if not intent.provider_reference or ":" not in intent.provider_reference:
            return None
        session, key = intent.provider_reference.split(":", 1)
        data = self.call(
            "GET",
            f"{self.base(secrets)}/sessions/{urllib.parse.quote(session)}?sk={urllib.parse.quote(key)}",
        )
        if not data.get("ResponseCode"):
            return None  # not answered yet
        approved = data.get("ResponseCode") == "00"
        return GatewayResult(
            status="approved" if approved else "declined",
            amount_cents=int(data["Amount"]) if data.get("Amount") else None,
            authorization_code=data.get("AuthorizationCode") or None,
            provider_reference=data.get("RetrievalReferenceNumber")
            or data.get("RetrivalReferenceNumber")
            or session,
            response_code=data.get("ResponseCode"),
            message=data.get("ResponseMessage") or None,
        )


GATEWAYS = {"sandbox": SandboxGateway, "azul": AzulGateway, "cardnet": CardnetGateway}


def gateway_for(name: str):
    try:
        return GATEWAYS[name]()
    except KeyError as exc:
        raise HTTPException(409, "La pasarela configurada no existe") from exc
