"""Payment providers for the SaaS subscription (Fase 4, block D2).

Every provider turns its own webhooks into ``BillingEventData`` so a single
processor (``lifecycle.apply``) changes subscriptions the same way whatever
the provider is. Changing provider (Stripe, Paddle, Azul...) means writing
another adapter, nothing else.

- ``SandboxProvider``: simulates checkout and payments inside Nexo
  (development and demos). Disabled in production.
- ``StripeProvider``: Checkout (mode subscription), customer portal, invoices
  and signed webhooks, with the standard library (no extra dependency).
"""

import base64
import hashlib
import hmac
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime

from fastapi import HTTPException

from app.db.database import settings

UNAVAILABLE = (
    "El cobro en línea aún no está disponible. Escribe al equipo de Nexo para cambiar de plan"
)


@dataclass(frozen=True)
class BillingEventData:
    event_id: str
    kind: str  # checkout.completed | payment.succeeded | payment.failed | subscription.canceled
    occurred_at: datetime
    institution_id: int | None = None
    plan_code: str | None = None
    interval: str | None = None
    customer_id: str | None = None
    subscription_id: str | None = None
    period_end: datetime | None = None
    extra: dict = field(default_factory=dict)


def from_timestamp(value) -> datetime | None:
    return datetime.fromtimestamp(int(value), UTC).replace(tzinfo=None) if value else None


# --- Sandbox -------------------------------------------------------------------


def _sign(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True).encode()
    body = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    mac = hmac.new(settings.secret_key.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{mac}"


def _unsign(token: str) -> dict:
    try:
        body, mac = token.rsplit(".", 1)
        expected = hmac.new(settings.secret_key.encode(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(mac, expected):
            raise ValueError
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(400, "El enlace de pago de prueba no es válido") from exc
    if payload.get("exp", 0) < time.time():
        raise HTTPException(400, "El enlace de pago de prueba venció. Empieza de nuevo")
    return payload


class SandboxProvider:
    name = "sandbox"

    @property
    def enabled(self) -> bool:
        return settings.app_environment != "production"

    def checkout(self, subscription, plan, interval: str, return_url: str) -> str:
        if not self.enabled:
            raise HTTPException(503, UNAVAILABLE)
        token = _sign(
            {
                "institution_id": subscription.institution_id,
                "plan_code": plan.code,
                "interval": interval,
                "exp": int(time.time()) + 3600,
            }
        )
        return f"{return_url}/sandbox?token={urllib.parse.quote(token)}"

    def portal(self, subscription, return_url: str) -> str:
        if not self.enabled:
            raise HTTPException(503, UNAVAILABLE)
        return return_url

    def invoices(self, subscription) -> list[dict]:
        return []

    def session(self, token: str) -> dict:
        return _unsign(token)

    def complete(self, token: str, outcome: str) -> list[BillingEventData]:
        """The fake payment page: what a real provider would send by webhook."""
        payload = _unsign(token)
        now = datetime.now(UTC).replace(tzinfo=None)
        institution = payload["institution_id"]
        reference = f"sbx_{institution}_{int(time.time() * 1000)}"
        common = {
            "occurred_at": now,
            "institution_id": institution,
            "customer_id": f"sbx_cus_{institution}",
            "subscription_id": f"sbx_sub_{institution}",
        }
        if outcome == "failed":
            return [
                BillingEventData(event_id=f"{reference}_failed", kind="payment.failed", **common)
            ]
        days = 365 if payload["interval"] == "yearly" else 30
        return [
            BillingEventData(
                event_id=f"{reference}_checkout",
                kind="checkout.completed",
                plan_code=payload["plan_code"],
                interval=payload["interval"],
                period_end=from_timestamp(time.time() + days * 86400),
                **common,
            )
        ]


# --- Stripe --------------------------------------------------------------------

STRIPE_API = "https://api.stripe.com/v1"
SIGNATURE_TOLERANCE = 300  # seconds


def _form(data: dict, prefix: str = "") -> list[tuple[str, str]]:
    """Stripe's nested form encoding: a[b][0][c]=value."""
    pairs = []
    for key, value in data.items():
        name = f"{prefix}[{key}]" if prefix else str(key)
        if isinstance(value, dict):
            pairs += _form(value, name)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                pairs += (
                    _form(item, f"{name}[{index}]")
                    if isinstance(item, dict)
                    else [(f"{name}[{index}]", str(item))]
                )
        elif value is not None:
            pairs.append((name, str(value).lower() if isinstance(value, bool) else str(value)))
    return pairs


class StripeProvider:
    name = "stripe"
    enabled = True

    def __init__(self, secret_key: str, webhook_secret: str, opener=None):
        self.secret_key = secret_key
        self.webhook_secret = webhook_secret
        self.opener = opener or urllib.request.urlopen

    def request(self, method: str, path: str, data: dict | None = None) -> dict:
        url = f"{STRIPE_API}{path}"
        body = None
        if data and method == "GET":
            url += "?" + urllib.parse.urlencode(_form(data))
        elif data:
            body = urllib.parse.urlencode(_form(data)).encode()
        request = urllib.request.Request(url, data=body, method=method)
        request.add_header("Authorization", f"Bearer {self.secret_key}")
        request.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            with self.opener(request, timeout=20) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            raise HTTPException(
                502, "El proveedor de pagos rechazó la operación. Intenta de nuevo más tarde"
            ) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise HTTPException(
                503, "No se pudo contactar al proveedor de pagos. Intenta de nuevo más tarde"
            ) from exc

    def checkout(self, subscription, plan, interval: str, return_url: str) -> str:
        price = plan.provider_yearly_price if interval == "yearly" else plan.provider_monthly_price
        if not price:
            raise HTTPException(409, f"El plan {plan.name} aún no tiene precio en el proveedor")
        metadata = {
            "institution_id": subscription.institution_id,
            "plan_code": plan.code,
            "interval": interval,
        }
        session = self.request(
            "POST",
            "/checkout/sessions",
            {
                "mode": "subscription",
                "line_items": [{"price": price, "quantity": 1}],
                "success_url": f"{return_url}?resultado=ok",
                "cancel_url": f"{return_url}?resultado=cancelado",
                "client_reference_id": subscription.institution_id,
                "customer": subscription.provider_customer_id,
                "metadata": metadata,
                "subscription_data": {"metadata": metadata},
            },
        )
        return session["url"]

    def portal(self, subscription, return_url: str) -> str:
        if not subscription.provider_customer_id:
            raise HTTPException(409, "Aún no hay un método de pago registrado")
        session = self.request(
            "POST",
            "/billing_portal/sessions",
            {"customer": subscription.provider_customer_id, "return_url": return_url},
        )
        return session["url"]

    def invoices(self, subscription) -> list[dict]:
        if not subscription.provider_customer_id:
            return []
        data = self.request(
            "GET", "/invoices", {"customer": subscription.provider_customer_id, "limit": 12}
        )
        return [
            {
                "number": item.get("number") or item["id"],
                "date": from_timestamp(item.get("created")),
                "amount": f"{item.get('amount_paid', item.get('total', 0)) / 100:.2f}",
                "currency": (item.get("currency") or "usd").upper(),
                "status": item.get("status") or "",
                "url": item.get("hosted_invoice_url"),
            }
            for item in data.get("data", [])
        ]

    def verify(self, body: bytes, header: str | None) -> dict:
        """Check the Stripe-Signature header (HMAC-SHA256 of "<t>.<body>")."""
        if not header:
            raise HTTPException(400, "Falta la firma del proveedor de pagos")
        parts = dict(item.split("=", 1) for item in header.split(",") if "=" in item)
        signatures = [
            v for k, v in (i.split("=", 1) for i in header.split(",") if "=" in i) if k == "v1"
        ]
        timestamp = parts.get("t", "0")
        expected = hmac.new(
            self.webhook_secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256
        ).hexdigest()
        if not any(hmac.compare_digest(expected, signature) for signature in signatures):
            raise HTTPException(400, "La firma del proveedor de pagos no es válida")
        if abs(time.time() - int(timestamp)) > SIGNATURE_TOLERANCE:
            raise HTTPException(400, "El aviso del proveedor de pagos es demasiado antiguo")
        return json.loads(body.decode())

    def parse(self, body: bytes, header: str | None) -> list[BillingEventData]:
        event = self.verify(body, header)
        item = event.get("data", {}).get("object", {})
        occurred = from_timestamp(event.get("created")) or datetime.now(UTC).replace(tzinfo=None)
        base = {"event_id": event["id"], "occurred_at": occurred}
        metadata = item.get("metadata") or {}
        kind = event.get("type")
        if kind == "checkout.session.completed":
            return [
                BillingEventData(
                    kind="checkout.completed",
                    institution_id=int(
                        item.get("client_reference_id") or metadata["institution_id"]
                    ),
                    plan_code=metadata.get("plan_code"),
                    interval=metadata.get("interval"),
                    customer_id=item.get("customer"),
                    subscription_id=item.get("subscription"),
                    **base,
                )
            ]
        if kind in ("invoice.paid", "invoice.payment_failed"):
            lines = (item.get("lines") or {}).get("data") or [{}]
            period_end = from_timestamp((lines[0].get("period") or {}).get("end"))
            return [
                BillingEventData(
                    kind="payment.succeeded" if kind == "invoice.paid" else "payment.failed",
                    customer_id=item.get("customer"),
                    subscription_id=item.get("subscription"),
                    period_end=period_end,
                    **base,
                )
            ]
        if kind == "customer.subscription.deleted":
            return [
                BillingEventData(
                    kind="subscription.canceled",
                    institution_id=int(metadata["institution_id"])
                    if metadata.get("institution_id")
                    else None,
                    customer_id=item.get("customer"),
                    subscription_id=item.get("id"),
                    **base,
                )
            ]
        return []  # other events are acknowledged and ignored


def provider():
    if settings.billing_provider == "stripe":
        return StripeProvider(settings.stripe_secret_key, settings.stripe_webhook_secret)
    return SandboxProvider()
