"""Subscription payments: sandbox, Stripe webhooks and «Plan y facturación» (Fase 4 D2)."""

import hashlib
import hmac
import io
import json
import time
import urllib.parse
from datetime import datetime, timedelta

import pytest
from test_write_audit import demo, entries  # noqa: F401  (shared fixtures)

from app.db.database import settings
from app.models import BillingEvent, Plan, PlatformAuditLog, Subscription
from app.services.billing.providers import StripeProvider

ORIGIN = {"origin": "http://localhost:5173"}
WEBHOOK_SECRET = "whsec_prueba"


def set_subscription(sessions, **values):
    with sessions() as db:
        row = db.query(Subscription).filter_by(institution_id=1).one()
        for key, value in values.items():
            if key == "plan":
                row.plan_id = db.query(Plan).filter_by(code=value).one().plan_id
            else:
                setattr(row, key, value)
        db.commit()


def subscription(sessions) -> Subscription:
    with sessions() as db:
        row = db.query(Subscription).filter_by(institution_id=1).one()
        row.plan  # loaded before leaving the session  # noqa: B018
        db.expunge_all()
        return row


def start_checkout(client, token, plan="profesional", interval="monthly"):
    response = client.post(
        "/billing/checkout",
        headers={**token, **ORIGIN},
        json={"plan_code": plan, "interval": interval},
    )
    assert response.status_code == 200, response.text
    url = response.json()["url"]
    assert url.startswith("http://localhost:5173/billing/sandbox?token=")
    return urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["token"][0]


def test_overview_shows_plan_usage_and_offers(demo):  # noqa: F811
    client, _sessions, tokens = demo
    overview = client.get("/billing/subscription", headers=tokens["admin"])
    assert overview.status_code == 200, overview.text
    body = overview.json()
    assert body["plan"]["code"] == "institucional" and body["status"] == "active"
    assert body["students"]["used"] >= 1 and body["students"]["limit"] is None
    assert [plan["code"] for plan in body["plans"]] == ["basico", "profesional"]
    assert body["provider"] == "sandbox" and body["online_checkout"] is True
    assert client.get("/billing/subscription", headers=tokens["docente"]).status_code == 403


def test_sandbox_checkout_activates_the_chosen_plan(demo):  # noqa: F811
    client, sessions, tokens = demo
    set_subscription(sessions, plan="basico", status="trialing", trial_ends_at=datetime.now())
    token = start_checkout(client, tokens["admin"], "profesional", "yearly")
    session = client.get(f"/billing/sandbox/session?token={token}", headers=tokens["admin"])
    assert (
        session.json()["plan"]["name"] == "Profesional" and session.json()["interval"] == "yearly"
    )
    paid = client.post(
        "/billing/sandbox/complete",
        headers=tokens["admin"],
        json={"token": token, "outcome": "paid"},
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["plan"]["code"] == "profesional" and paid.json()["status"] == "active"
    row = subscription(sessions)
    assert row.interval == "yearly" and row.trial_ends_at is None
    assert row.current_period_end > datetime.now() + timedelta(days=360)
    assert row.provider_customer_id == "sbx_cus_1"
    assert entries(sessions, "billing.checkout_started")
    assert entries(sessions, "billing.sandbox_payment")
    with sessions() as db:
        assert db.query(BillingEvent).filter_by(kind="checkout.completed").count() == 1
        assert (
            db.query(PlatformAuditLog).filter_by(action="billing.checkout.completed").count() == 1
        )


def test_a_failed_payment_marks_overdue_and_a_later_payment_clears_it(demo):  # noqa: F811
    client, sessions, tokens = demo
    set_subscription(sessions, plan="basico", status="active")
    token = start_checkout(client, tokens["admin"])
    failed = client.post(
        "/billing/sandbox/complete",
        headers=tokens["admin"],
        json={"token": token, "outcome": "failed"},
    )
    assert failed.json()["status"] == "past_due"
    assert subscription(sessions).past_due_since is not None
    time.sleep(0.01)  # the payment happens after the failure
    paid = client.post(
        "/billing/sandbox/complete",
        headers=tokens["admin"],
        json={"token": token, "outcome": "paid"},
    )
    assert paid.json()["status"] == "active"
    assert subscription(sessions).past_due_since is None


def test_sandbox_tokens_cannot_be_forged_or_reused_elsewhere(demo):  # noqa: F811
    client, _sessions, tokens = demo
    token = start_checkout(client, tokens["admin"])
    forged = token[:-4] + ("0000" if not token.endswith("0000") else "1111")
    bad = client.post(
        "/billing/sandbox/complete",
        headers=tokens["admin"],
        json={"token": forged, "outcome": "paid"},
    )
    assert bad.status_code == 400 and "no es válido" in bad.json()["detail"]
    assert (
        client.post(
            "/billing/checkout",
            headers={**tokens["admin"], **ORIGIN},
            json={"plan_code": "institucional"},
        ).status_code
        == 404
    )  # custom plans are not sold online


def test_production_never_simulates_payments(demo, monkeypatch):  # noqa: F811
    client, _sessions, tokens = demo
    monkeypatch.setattr(settings, "app_environment", "production")
    overview = client.get("/billing/subscription", headers=tokens["admin"]).json()
    assert overview["online_checkout"] is False
    refused = client.post(
        "/billing/checkout",
        headers={**tokens["admin"], **ORIGIN},
        json={"plan_code": "profesional"},
    )
    assert refused.status_code == 503 and "Escribe al equipo de Nexo" in refused.json()["detail"]
    assert (
        client.post(
            "/billing/sandbox/complete",
            headers=tokens["admin"],
            json={"token": "x" * 20, "outcome": "paid"},
        ).status_code
        == 404
    )


# --- Stripe --------------------------------------------------------------------


@pytest.fixture
def stripe(monkeypatch):
    monkeypatch.setattr(settings, "billing_provider", "stripe")
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_prueba")
    monkeypatch.setattr(settings, "stripe_webhook_secret", WEBHOOK_SECRET)


def signed(event: dict, secret=WEBHOOK_SECRET, at=None):
    body = json.dumps(event).encode()
    timestamp = str(int(at or time.time()))
    signature = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256)
    return body, {"stripe-signature": f"t={timestamp},v1={signature.hexdigest()}"}


def send(client, event, **kwargs):
    body, headers = signed(event, **kwargs)
    return client.post(
        "/billing/webhooks/stripe",
        content=body,
        headers={**headers, "content-type": "application/json"},
    )


def stripe_event(event_id, kind, item, created=None):
    return {
        "id": event_id,
        "type": kind,
        "created": int(created or time.time()),
        "data": {"object": item},
    }


def test_stripe_webhooks_drive_the_subscription(demo, stripe):  # noqa: F811
    client, sessions, _tokens = demo
    set_subscription(sessions, plan="basico", status="trialing")
    started = int(time.time()) - 100
    completed = stripe_event(
        "evt_1",
        "checkout.session.completed",
        {
            "client_reference_id": "1",
            "customer": "cus_123",
            "subscription": "sub_123",
            "metadata": {"institution_id": "1", "plan_code": "profesional", "interval": "monthly"},
        },
        created=started,
    )
    first = send(client, completed)
    assert first.status_code == 200, first.text
    assert first.json()["outcomes"] == ["trialing → active"]
    assert send(client, completed).json()["outcomes"] == ["repetido"]  # retries apply once
    row = subscription(sessions)
    assert row.plan.code == "profesional" and row.provider_customer_id == "cus_123"

    failed = stripe_event(
        "evt_2", "invoice.payment_failed", {"customer": "cus_123"}, created=started + 50
    )
    assert send(client, failed).json()["outcomes"] == ["active → past_due"]
    # A payment notice older than the failure arrives late: it changes nothing.
    late = stripe_event("evt_3", "invoice.paid", {"customer": "cus_123"}, created=started + 10)
    assert "ignorado" in send(client, late).json()["outcomes"][0]
    assert subscription(sessions).status == "past_due"

    paid = stripe_event(
        "evt_4",
        "invoice.paid",
        {
            "customer": "cus_123",
            "subscription": "sub_123",
            "lines": {"data": [{"period": {"end": int(time.time()) + 30 * 86400}}]},
        },
        created=started + 60,
    )
    assert send(client, paid).json()["outcomes"] == ["past_due → active"]
    canceled = stripe_event(
        "evt_5",
        "customer.subscription.deleted",
        {"id": "sub_123", "customer": "cus_123", "metadata": {"institution_id": "1"}},
        created=started + 70,
    )
    assert send(client, canceled).json()["outcomes"] == ["active → read_only"]
    ignored = stripe_event("evt_6", "customer.created", {"id": "cus_9"})
    assert send(client, ignored).json()["outcomes"] == []


def test_stripe_webhooks_must_be_signed_and_recent(demo, stripe):  # noqa: F811
    client, _sessions, _tokens = demo
    event = stripe_event("evt_x", "invoice.paid", {"customer": "cus_123"})
    assert send(client, event, secret="whsec_otro").status_code == 400
    assert send(client, event, at=time.time() - 3600).status_code == 400
    unsigned = client.post("/billing/webhooks/stripe", content=json.dumps(event).encode())
    assert unsigned.status_code == 400


def test_webhook_route_is_closed_without_stripe(demo):  # noqa: F811
    client, _sessions, _tokens = demo
    assert client.post("/billing/webhooks/stripe", content=b"{}").status_code == 404


def test_stripe_checkout_portal_and_invoices_requests():
    calls = []

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def opener(request, timeout):
        calls.append(request)
        if "invoices" in request.full_url:
            payload = {
                "data": [
                    {
                        "id": "in_1",
                        "number": "NEXO-0001",
                        "created": 1764000000,
                        "amount_paid": 24900,
                        "currency": "usd",
                        "status": "paid",
                        "hosted_invoice_url": "https://pay.stripe.com/i/1",
                    }
                ]
            }
        else:
            payload = {"url": "https://checkout.stripe.com/c/1"}
        return Response(json.dumps(payload).encode())

    class Sub:
        institution_id = 7
        provider_customer_id = "cus_7"

    class PlanStub:
        code, name = "profesional", "Profesional"
        provider_monthly_price, provider_yearly_price = "price_m", "price_y"

    stripe = StripeProvider("sk_test_x", WEBHOOK_SECRET, opener=opener)
    url = stripe.checkout(Sub(), PlanStub(), "yearly", "https://colegio.nexo.do/billing")
    assert url == "https://checkout.stripe.com/c/1"
    form = dict(urllib.parse.parse_qsl(calls[0].data.decode()))
    assert form["mode"] == "subscription" and form["line_items[0][price]"] == "price_y"
    assert form["client_reference_id"] == "7" and form["customer"] == "cus_7"
    assert form["subscription_data[metadata][institution_id]"] == "7"
    assert form["success_url"] == "https://colegio.nexo.do/billing?resultado=ok"
    assert calls[0].get_header("Authorization") == "Bearer sk_test_x"
    assert stripe.portal(Sub(), "https://colegio.nexo.do/billing").startswith("https://")
    invoices = stripe.invoices(Sub())
    assert invoices[0]["number"] == "NEXO-0001" and invoices[0]["amount"] == "249.00"
    assert "customer=cus_7" in calls[-1].full_url
