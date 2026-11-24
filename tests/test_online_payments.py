"""Online card payments of families (Fase 4, block E1-E3)."""

import io
import json
from decimal import Decimal

import pytest
from cryptography.fernet import Fernet
from test_write_audit import demo, entries  # noqa: F401  (shared fixtures)

from app.db.database import settings
from app.models import (
    CashClosing,
    Guardian,
    InstitutionSettings,
    OnlinePayment,
    Payment,
    PaymentGatewayConfig,
    Role,
    Student,
    StudentGuardian,
    User,
)
from app.security import hash_password
from app.services.payments.gateways import AzulGateway, CardnetGateway
from app.services.payments.secrets import decrypt

ORIGIN = {"origin": "http://localhost:5173"}
GUARDIAN_PASSWORD = "TutoraPagos2026!"
KEY = Fernet.generate_key().decode()


@pytest.fixture
def family(demo, monkeypatch):  # noqa: F811
    """The demo student with RD$2,500 due and a guardian who may see finances."""
    client, sessions, tokens = demo
    monkeypatch.setattr(settings, "payments_encryption_key", KEY)
    with sessions() as db:
        student = db.query(Student).first().student_id
        role = Role(name="guardian", description="Tutoría")
        guardian = Guardian(
            first_name="Rosa", last_name="Peña", email="rosa@ejemplo.do", telephone="809"
        )
        db.add_all([role, guardian])
        db.flush()
        db.add(
            StudentGuardian(
                student_id=student, guardian_id=guardian.guardian_id, relationship="Madre"
            )
        )
        db.add(
            User(
                username="rosa.pena",
                email="rosa@ejemplo.do",
                password=hash_password(GUARDIAN_PASSWORD),
                role_id=role.role_id,
                guardian_id=guardian.guardian_id,
            )
        )
        db.commit()
    charge = client.post(
        f"/finance/students/{student}/charges",
        headers=tokens["admin"],
        json={"description": "Mensualidad", "amount": "2500.00"},
    )
    assert charge.status_code == 200, charge.text
    login = client.post(
        "/auth/login", json={"username": "rosa.pena", "password": GUARDIAN_PASSWORD}
    )
    guardian_token = {"Authorization": "Bearer " + login.json()["access_token"]}
    return client, sessions, tokens, guardian_token, student


def configure(client, token, **changes):
    body = {
        "enabled": True,
        "gateway": "sandbox",
        "merchant_id": "39038540035",
        "merchant_name": "Instituto Técnico Horizonte",
        "min_amount": "100.00",
        **changes,
    }
    return client.put("/online-payments/config/gateway", headers=token, json=body)


def pay(client, token, student, amount="1000.00"):
    return client.post(
        "/online-payments",
        headers={**token, **ORIGIN},
        json={"allocations": [{"student_id": student, "amount": amount}]},
    )


def balance(client, token, student) -> Decimal:
    return Decimal(client.get(f"/finance/students/{student}", headers=token).json()["balance"])


def test_a_family_pays_by_card_and_the_payment_posts_once(family):
    client, sessions, tokens, guardian, student = family
    assert client.get("/online-payments/options", headers=guardian).json()["enabled"] is False
    assert configure(client, tokens["admin"]).status_code == 200
    options = client.get("/online-payments/options", headers=guardian).json()
    assert options["enabled"] is True and options["students"][0]["balance"] == "2500.00"

    started = pay(client, guardian, student)
    assert started.status_code == 200, started.text
    redirect = started.json()["redirect"]
    assert redirect["url"] == "http://localhost:5173/pagos/sandbox"
    public_id = started.json()["id"]
    done = client.post(
        f"/online-payments/{public_id}/complete", json={"params": {"outcome": "approved"}}
    )
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "approved" and done.json()["receipts"][0].startswith("REC-")
    assert balance(client, tokens["admin"], student) == Decimal("1500.00")
    # The bank's redirect is repeated (reload): nothing is posted twice.
    again = client.post(
        f"/online-payments/{public_id}/complete", json={"params": {"outcome": "approved"}}
    )
    assert again.json()["status"] == "approved"
    with sessions() as db:
        payments = db.query(Payment).filter_by(method="online").all()
        assert len(payments) == 1 and payments[0].amount == Decimal("1000.00")
    assert client.get(f"/online-payments/{public_id}", headers=guardian).json()["status"] == (
        "approved"
    )


def test_a_declined_card_posts_nothing(family):
    client, _sessions, tokens, guardian, student = family
    configure(client, tokens["admin"])
    public_id = pay(client, guardian, student).json()["id"]
    declined = client.post(
        f"/online-payments/{public_id}/complete", json={"params": {"outcome": "declined"}}
    )
    assert declined.json()["status"] == "declined" and declined.json()["receipts"] == []
    assert balance(client, tokens["admin"], student) == Decimal("2500.00")


def test_amounts_and_payers_are_checked_by_the_server(family):
    client, sessions, tokens, guardian, student = family
    configure(client, tokens["admin"], min_amount="500.00")
    too_much = pay(client, guardian, student, "3000.00")
    assert too_much.status_code == 422 and "balance pendiente" in too_much.json()["detail"]
    too_little = pay(client, guardian, student, "100.00")
    assert too_little.status_code == 422 and "mínimo" in too_little.json()["detail"]
    with sessions() as db:
        other = Student(
            first_name="Ajeno",
            last_name="X",
            email="ajeno@x.do",
            enrollment_number="X-9",
            telephone="1",
            address="a",
            career_id=db.query(Student).first().career_id,
        )
        db.add(other)
        db.commit()
        stranger = other.student_id
    assert pay(client, guardian, stranger).status_code == 403
    staff = pay(client, tokens["admin"], student)
    assert staff.status_code == 403 and "caja" in staff.json()["detail"]


def test_students_pay_only_if_the_institution_shows_them_their_finances(family):
    client, sessions, tokens, _guardian, student = family
    configure(client, tokens["admin"])
    with sessions() as db:
        if db.query(InstitutionSettings).count() == 0:
            db.add(InstitutionSettings(institution_name="Demo", students_view_finance=False))
        db.query(InstitutionSettings).update({"students_view_finance": False})
        db.commit()
    assert pay(client, tokens["estudiante"], student).status_code == 403
    with sessions() as db:
        db.query(InstitutionSettings).update({"students_view_finance": True})
        db.commit()
    assert pay(client, tokens["estudiante"], student).status_code == 200


def test_an_approved_card_posts_even_after_the_cash_closing(family):
    client, sessions, tokens, guardian, student = family
    configure(client, tokens["admin"])
    public_id = pay(client, guardian, student, "2500.00").json()["id"]
    # Meanwhile the cashier also received the full amount and closed the day.
    from app.services.business_time import business_date

    client.post(
        f"/finance/students/{student}/payments",
        headers=tokens["admin"],
        json={"amount": "2500.00", "reference": "CAJA-1"},
    )
    with sessions() as db:
        db.add(
            CashClosing(
                closing_date=business_date(),
                closed_by=1,
                total_payments=Decimal("2500.00"),
                payment_count=1,
            )
        )
        db.commit()
    done = client.post(
        f"/online-payments/{public_id}/complete", json={"params": {"outcome": "approved"}}
    )
    assert done.json()["status"] == "approved"
    with sessions() as db:
        assert db.query(OnlinePayment).filter_by(public_id=public_id).one().overpaid is True


def test_gateway_secrets_are_encrypted_masked_and_audited(family):
    client, sessions, tokens, _guardian, _student = family
    saved = configure(client, tokens["admin"], gateway="azul", auth_key="clave-secreta-azul-1234")
    assert saved.status_code == 200, saved.text
    assert saved.json()["auth_key"].endswith("1234") and "clave" not in saved.json()["auth_key"]
    with sessions() as db:
        row = db.query(PaymentGatewayConfig).one()
        assert "clave-secreta" not in row.secrets
        assert decrypt(row.secrets)["auth_key"] == "clave-secreta-azul-1234"
    # Saving again without the key keeps it.
    configure(client, tokens["admin"], gateway="azul", merchant_name="Otro nombre")
    with sessions() as db:
        assert decrypt(db.query(PaymentGatewayConfig).one().secrets)["auth_key"].endswith("1234")
    logged = entries(sessions, "online_payments.configured")
    assert logged and "clave-secreta" not in json.dumps(logged)
    assert configure(client, tokens["docente"]).status_code == 403
    assert configure(client, tokens["admin"], gateway="cardnet", merchant_id="").status_code == 422


def test_production_never_uses_the_test_gateway(family, monkeypatch):
    client, _sessions, tokens, guardian, student = family
    configure(client, tokens["admin"])
    monkeypatch.setattr(settings, "app_environment", "production")
    assert client.get("/online-payments/options", headers=guardian).json()["enabled"] is False
    assert pay(client, guardian, student).status_code == 409


# --- Azul and CardNet adapters ---------------------------------------------------


class Intent:
    public_id = "a" * 32
    online_payment_id = 42
    amount = Decimal("1500.50")
    provider_reference = None


class Config:
    merchant_id = "39038540035"
    merchant_name = "Instituto Técnico Horizonte"


def test_azul_request_and_answer_signatures():
    azul = AzulGateway()
    secrets = {"auth_key": "llave-azul", "environment": "test"}
    redirect = azul.start(Intent(), Config(), secrets, "https://colegio.nexo.do/pagos")
    fields = redirect.fields
    assert redirect.method == "POST" and redirect.url == AzulGateway.TEST_URL
    assert fields["Amount"] == "150050" and fields["OrderNumber"] == "a" * 15
    assert fields["AuthHash"] == AzulGateway.signature(
        [fields[key] for key in AzulGateway.REQUEST_FIELDS], "llave-azul"
    )
    answer = {
        "OrderNumber": "a" * 15,
        "Amount": "150050",
        "AuthorizationCode": "OK1234",
        "DateTime": "20261126101500",
        "ResponseCode": "ISO8583",
        "IsoCode": "00",
        "ResponseMessage": "APROBADA",
        "ErrorDescription": "",
        "RRN": "123456789012",
        "AzulOrderId": "998877",
    }
    answer["AuthHash"] = AzulGateway.signature(
        [answer[key] for key in AzulGateway.RESPONSE_FIELDS], "llave-azul"
    )
    result = azul.verify(answer, Intent(), Config(), secrets)
    assert result.status == "approved" and result.amount_cents == 150050
    assert result.authorization_code == "OK1234" and result.provider_reference == "998877"
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        azul.verify({**answer, "Amount": "1"}, Intent(), Config(), secrets)  # tampered
    declined = {**answer, "IsoCode": "51", "ResponseMessage": "FONDOS INSUFICIENTES"}
    declined["AuthHash"] = AzulGateway.signature(
        [declined[key] for key in AzulGateway.RESPONSE_FIELDS], "llave-azul"
    )
    assert azul.verify(declined, Intent(), Config(), secrets).status == "declined"


def test_cardnet_session_and_server_to_server_result():
    calls = []

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def opener(request, timeout):
        calls.append(request)
        if request.get_method() == "POST":
            return Response(json.dumps({"SESSION": "S1", "session-key": "K1"}).encode())
        return Response(
            json.dumps(
                {
                    "ResponseCode": "00",
                    "AuthorizationCode": "CN777",
                    "RetrievalReferenceNumber": "R1",
                    "Amount": "150050",
                }
            ).encode()
        )

    cardnet = CardnetGateway(opener=opener)
    intent = Intent()
    secrets = {"terminal": "T001", "environment": "test"}
    redirect = cardnet.start(intent, Config(), secrets, "https://colegio.nexo.do/pagos")
    assert redirect.fields == {"SESSION": "S1"} and redirect.url.endswith("/authorize")
    sent = json.loads(calls[0].data)
    assert sent["Amount"] == "150050" and sent["MerchantTerminal"] == "T001"
    assert intent.provider_reference == "S1:K1"
    result = cardnet.verify({}, intent, Config(), secrets)
    assert result.status == "approved" and result.authorization_code == "CN777"
    assert calls[-1].full_url.endswith("/sessions/S1?sk=K1")


# --- Reconciliation (block E5) ---------------------------------------------------


def test_reconciliation_list_report_and_supervisor_resolution(family):
    client, sessions, tokens, guardian, student = family
    configure(client, tokens["admin"])
    approved = pay(client, guardian, student, "500.00").json()["id"]
    client.post(f"/online-payments/{approved}/complete", json={"params": {"outcome": "approved"}})
    lost = pay(client, guardian, student, "700.00").json()["id"]  # the payer never came back

    listed = client.get("/online-payments?limit=10", headers=tokens["admin"])
    assert listed.status_code == 200 and listed.headers["X-Total-Count"] == "2"
    first = listed.json()[1]
    assert first["status"] == "approved" and first["payer"] == "rosa.pena"
    assert first["students"][0]["amount"] == "500.00" and first["students"][0]["name"]
    pending = client.get("/online-payments?status=pending", headers=tokens["admin"]).json()
    assert [row["id"] for row in pending] == [lost]
    assert client.get("/online-payments", headers=tokens["docente"]).status_code == 403

    from app.services.business_time import business_date

    report = client.get(
        f"/online-payments/report/daily?day={business_date()}", headers=tokens["admin"]
    ).json()
    assert report["approved_amount"] == "500.00"

    missing_code = client.post(
        f"/online-payments/{lost}/resolve",
        headers=tokens["admin"],
        json={"outcome": "approved", "reason": "Visto en el portal del banco"},
    )
    assert missing_code.status_code == 422
    resolved = client.post(
        f"/online-payments/{lost}/resolve",
        headers=tokens["admin"],
        json={
            "outcome": "approved",
            "authorization_code": "AZ9911",
            "reason": "Visto en el portal del banco",
        },
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["status"] == "approved" and resolved.json()["receipts"]
    assert balance(client, tokens["admin"], student) == Decimal("1300.00")
    assert entries(sessions, "online_payment.resolved")
    again = client.post(
        f"/online-payments/{lost}/resolve",
        headers=tokens["admin"],
        json={"outcome": "declined", "reason": "Segundo intento"},
    )
    assert again.status_code == 409


def test_stale_intents_expire_but_a_late_bank_answer_still_counts(family):
    client, sessions, tokens, guardian, student = family
    configure(client, tokens["admin"])
    public_id = pay(client, guardian, student, "400.00").json()["id"]
    from datetime import datetime, timedelta

    from app.db.tenant import set_tenant
    from app.services.payments.intents import expire_stale

    with sessions() as db:
        set_tenant(db, 1)
        assert expire_stale(db, datetime.now() + timedelta(minutes=30))["expired"] == 0
        assert expire_stale(db, datetime.now() + timedelta(hours=2))["expired"] == 1
        db.commit()
    with sessions() as db:
        assert db.query(OnlinePayment).filter_by(public_id=public_id).one().status == "expired"
    late = client.post(
        f"/online-payments/{public_id}/complete", json={"params": {"outcome": "approved"}}
    )
    assert late.json()["status"] == "approved"
    assert balance(client, tokens["admin"], student) == Decimal("2100.00")
