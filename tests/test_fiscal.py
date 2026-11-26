"""Fiscal receipts: issuer, DGII sequences, receipts on payments, credit notes (Fase 4 F)."""

import io
import threading
from datetime import timedelta
from decimal import Decimal

import pytest
from db_support import TEST_DATABASE_URL
from pypdf import PdfReader
from test_write_audit import demo, entries  # noqa: F401  (shared fixtures)

from app.models import FinanceEvent, FiscalDocument, FiscalSequence, Student, User
from app.services.business_time import business_date
from app.services.fiscal.rules import (
    clean_tax_id,
    number_text,
    receipt_type,
    split_itbis,
    valid_cedula,
    valid_rnc,
)


def with_rnc_check(first8: str) -> str:
    weights = (7, 9, 8, 6, 5, 4, 3, 2)
    remainder = sum(int(d) * w for d, w in zip(first8, weights, strict=True)) % 11
    return first8 + str(2 if remainder == 0 else 1 if remainder == 1 else 11 - remainder)


def with_cedula_check(first10: str) -> str:
    total = 0
    for index, digit in enumerate(first10):
        product = int(digit) * (1 if index % 2 == 0 else 2)
        total += product // 10 + product % 10
    return first10 + str((10 - total % 10) % 10)


RNC = with_rnc_check("13101234")  # the institution
BUYER_RNC = with_rnc_check("10100004")


def test_formats_ids_and_itbis():
    assert number_text("B02", 1) == "B0200000001"
    assert number_text("E32", 15) == "E320000000015"
    assert receipt_type("ncf", "") == "B02" and receipt_type("ncf", RNC) == "B01"
    assert receipt_type("ecf", "") == "E32" and receipt_type("ecf", RNC) == "E31"
    assert valid_rnc(RNC) and not valid_rnc(RNC[:-1] + str((int(RNC[-1]) + 1) % 10))
    cedula = with_cedula_check("0011234567")
    assert valid_cedula(cedula) and clean_tax_id(f"{cedula[:3]}-{cedula[3:10]}-{cedula[10]}")
    assert split_itbis(118000, Decimal("18")) == (100000, 18000)
    assert split_itbis(250000, Decimal("0")) == (250000, 0)
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        clean_tax_id("123456789")


def setup_fiscal(client, token, issue_on="payment", **sequence):
    profile = client.put(
        "/fiscal/profile",
        headers=token,
        json={
            "enabled": True,
            "mode": "ncf",
            "rnc": RNC,
            "legal_name": "Instituto Técnico Horizonte, SRL",
            "fiscal_address": "Av. Bolívar 100, Santo Domingo",
            "issue_on": issue_on,
        },
    )
    assert profile.status_code == 200, profile.text
    for doc_type in ("B01", "B02", "B04"):
        body = {
            "doc_type": doc_type,
            "range_start": 1,
            "range_end": 100,
            "expires_on": str(business_date() + timedelta(days=365)),
        }
        added = client.post("/fiscal/sequences", headers=token, json={**body, **sequence})
        assert added.status_code == 200, added.text


@pytest.fixture
def account(demo):  # noqa: F811
    """The demo student owes tuition (exempt) and a uniform (ITBIS 18 % included)."""
    client, sessions, tokens = demo
    with sessions() as db:
        student = db.query(Student).first().student_id
    admin = tokens["admin"]
    for body in (
        {"description": "Mensualidad", "amount": "2000.00"},
        {"description": "Uniforme", "amount": "1180.00", "itbis_rate": "18"},
    ):
        created = client.post(f"/finance/students/{student}/charges", headers=admin, json=body)
        assert created.status_code == 200, created.text
    return client, sessions, tokens, student


def pay(client, token, student, amount, reference):
    response = client.post(
        f"/finance/students/{student}/payments",
        headers=token,
        json={"amount": amount, "reference": reference},
    )
    assert response.status_code == 200, response.text
    return response


def documents(sessions):
    with sessions() as db:
        rows = db.query(FiscalDocument).order_by(FiscalDocument.fiscal_document_id).all()
        for row in rows:
            row.lines  # noqa: B018
        db.expunge_all()
        return rows


def test_the_issuer_needs_a_valid_rnc_and_ranges_never_overlap(demo):  # noqa: F811
    client, _sessions, tokens = demo
    bad = client.put(
        "/fiscal/profile",
        headers=tokens["admin"],
        json={"enabled": True, "mode": "ncf", "rnc": "123456789", "legal_name": "X"},
    )
    assert bad.status_code == 422
    setup_fiscal(client, tokens["admin"])
    overlap = client.post(
        "/fiscal/sequences",
        headers=tokens["admin"],
        json={"doc_type": "B02", "range_start": 50, "range_end": 150},
    )
    assert overlap.status_code == 409
    assert client.get("/fiscal/profile", headers=tokens["docente"]).status_code == 403
    assert entries(_sessions, "fiscal.profile_saved")


def test_a_payment_gets_its_consumer_receipt_with_itbis(account):
    client, sessions, tokens, student = account
    setup_fiscal(client, tokens["admin"])
    pay(client, tokens["admin"], student, "3180.00", "CAJA-1")
    [receipt] = documents(sessions)
    assert receipt.doc_type == "B02" and receipt.ncf == "B0200000001"
    assert [(line.description, line.line_total) for line in receipt.lines] == [
        ("Mensualidad", Decimal("2000.00")),
        ("Uniforme", Decimal("1180.00")),
    ]
    assert receipt.itbis == Decimal("180.00") and receipt.subtotal == Decimal("3000.00")
    assert receipt.total == Decimal("3180.00")
    pdf = client.get(f"/fiscal/documents/{receipt.fiscal_document_id}.pdf", headers=tokens["admin"])
    text = "".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf.content)).pages)
    assert "B0200000001" in text and RNC in text and "Válido hasta" in text


def test_a_partial_payment_settles_the_oldest_charge_first(account):
    client, sessions, tokens, student = account
    setup_fiscal(client, tokens["admin"])
    pay(client, tokens["admin"], student, "1500.00", "CAJA-A")
    pay(client, tokens["admin"], student, "1680.00", "CAJA-B")
    first, second = documents(sessions)
    assert [(line.description, line.line_total) for line in first.lines] == [
        ("Mensualidad", Decimal("1500.00"))
    ]
    assert [(line.description, line.line_total) for line in second.lines] == [
        ("Mensualidad", Decimal("500.00")),
        ("Uniforme", Decimal("1180.00")),
    ]
    assert second.ncf == "B0200000002"


def second_supervisor(client, sessions):
    """Nobody reverses their own payment: another account with the admin role."""
    from app.models import Role
    from app.security import hash_password

    with sessions() as db:
        role = db.query(Role).filter_by(name="admin").first()
        db.add(
            User(
                username="supervisora",
                email="supervisora@ejemplo.do",
                password=hash_password("Supervisora2026!"),
                role_id=role.role_id,
            )
        )
        db.commit()
    login = client.post(
        "/auth/login", json={"username": "supervisora", "password": "Supervisora2026!"}
    )
    return {"Authorization": "Bearer " + login.json()["access_token"]}


def test_tax_credit_receipts_and_credit_notes_on_reversal(account):
    client, sessions, tokens, student = account
    setup_fiscal(client, tokens["admin"])
    bill_to = client.put(
        f"/fiscal/accounts/{student}/bill-to",
        headers=tokens["admin"],
        json={"name": "Constructora Peña, SRL", "tax_id": BUYER_RNC},
    )
    assert bill_to.status_code == 200, bill_to.text
    pay(client, tokens["admin"], student, "2000.00", "CAJA-RNC")
    [receipt] = documents(sessions)
    assert receipt.doc_type == "B01" and receipt.buyer_tax_id == BUYER_RNC
    supervisor = second_supervisor(client, sessions)
    reversed_ = client.post(
        f"/finance/students/{student}/transactions/payment/{receipt.payment_id}/reverse",
        headers=supervisor,
        json={"reason": "Pago duplicado por error"},
    )
    assert reversed_.status_code == 200, reversed_.text
    original, note = documents(sessions)
    assert note.doc_type == "B04" and note.ncf == "B0400000001"
    assert note.affected_document_id == original.fiscal_document_id
    assert note.total == original.total and note.buyer_tax_id == BUYER_RNC
    listed = client.get(f"/fiscal/payments/{receipt.payment_id}", headers=tokens["admin"]).json()
    assert [row["doc_type"] for row in listed] == ["B01", "B04"]
    assert (
        client.put(
            f"/fiscal/accounts/{student}/bill-to", headers=tokens["admin"], json={"tax_id": "123"}
        ).status_code
        == 422
    )


def test_without_a_valid_range_the_payment_posts_and_the_receipt_waits(account):
    client, sessions, tokens, student = account
    setup_fiscal(client, tokens["admin"], expires_on=str(business_date() - timedelta(days=1)))
    pay(client, tokens["admin"], student, "2000.00", "CAJA-SIN-NCF")
    assert documents(sessions) == []
    with sessions() as db:
        pending = db.query(FinanceEvent).filter_by(action="fiscal.pending").one()
        assert "vigente" in pending.detail
        payment_id = __import__("json").loads(pending.detail)["payment_id"]
    alerts = client.get("/fiscal/sequences", headers=tokens["admin"]).json()["alerts"]
    assert {alert["kind"] for alert in alerts} == {"expired"}
    client.post(
        "/fiscal/sequences",
        headers=tokens["admin"],
        json={"doc_type": "B02", "range_start": 101, "range_end": 200},
    )
    issued = client.post(f"/fiscal/payments/{payment_id}/issue", headers=tokens["admin"])
    assert issued.status_code == 200 and issued.json()["ncf"] == "B0200000101"
    again = client.post(f"/fiscal/payments/{payment_id}/issue", headers=tokens["admin"])
    assert again.json()["ncf"] == "B0200000101"  # one receipt per payment


def test_on_request_mode_issues_only_when_asked(account):
    client, sessions, tokens, student = account
    setup_fiscal(client, tokens["admin"], issue_on="request")
    pay(client, tokens["admin"], student, "1000.00", "CAJA-SOLICITUD")
    assert documents(sessions) == []


def test_low_ranges_raise_an_alert(account):
    client, sessions, tokens, student = account
    setup_fiscal(client, tokens["admin"])
    with sessions() as db:
        db.query(FiscalSequence).filter_by(doc_type="B02").update({"next_number": 95})
        db.commit()
    alerts = client.get("/fiscal/sequences", headers=tokens["admin"]).json()["alerts"]
    assert any(alert["kind"] == "low" and "Quedan 6" in alert["message"] for alert in alerts)


@pytest.mark.skipif(TEST_DATABASE_URL is None, reason="Requiere PostgreSQL (concurrencia real)")
def test_concurrent_payments_never_share_a_number(account):
    client, sessions, tokens, student = account
    setup_fiscal(client, tokens["admin"])
    codes = []

    def run(index):
        response = client.post(
            f"/finance/students/{student}/payments",
            headers=tokens["admin"],
            json={"amount": "100.00", "reference": f"PAR-{index}"},
        )
        codes.append(response.status_code)

    threads = [threading.Thread(target=run, args=(index,)) for index in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    numbers = [row.ncf for row in documents(sessions)]
    assert codes == [200] * 6 and len(numbers) == 6 and len(set(numbers)) == 6
    assert sorted(numbers) == [f"B02{index:08d}" for index in range(1, 7)]


# --- Voids and DGII reports (blocks F3-F4) ----------------------------------------


def test_voids_and_dgii_607_608(account):
    client, sessions, tokens, student = account
    setup_fiscal(client, tokens["admin"])
    pay(client, tokens["admin"], student, "3180.00", "CAJA-607")
    client.put(
        f"/fiscal/accounts/{student}/bill-to",
        headers=tokens["admin"],
        json={"name": "Constructora Peña, SRL", "tax_id": BUYER_RNC},
    )
    client.post(
        f"/finance/students/{student}/charges",
        headers=tokens["admin"],
        json={"description": "Transporte", "amount": "500.00"},
    )
    pay(client, tokens["admin"], student, "500.00", "CAJA-608")
    consumer, credit = documents(sessions)
    assert credit.doc_type == "B01"
    bad_reason = client.post(
        f"/fiscal/documents/{credit.fiscal_document_id}/void",
        headers=tokens["admin"],
        json={"reason": "99", "note": "Error de datos"},
    )
    assert bad_reason.status_code == 422
    voided = client.post(
        f"/fiscal/documents/{credit.fiscal_document_id}/void",
        headers=tokens["admin"],
        json={"reason": "04", "note": "RNC equivocado"},
    )
    assert voided.status_code == 200 and voided.json()["status"] == "voided"
    assert entries(sessions, "fiscal.voided")

    month = business_date().strftime("%Y-%m")
    sales = client.get(f"/fiscal/reports/607.txt?month={month}", headers=tokens["admin"])
    assert sales.status_code == 200
    assert f"DGII_F_607_{RNC}_{month.replace('-', '')}.txt" in sales.headers["content-disposition"]
    header, *rows = sales.text.strip().split("\n")
    assert header == f"607|{RNC}|{month.replace('-', '')}|1"
    fields = rows[0].split("|")
    assert len(fields) == 23
    assert fields[2] == consumer.ncf and fields[0] == "" and fields[4] == "01"
    assert fields[7] == "3000.00" and fields[8] == "180.00" and fields[16] == "3180.00"

    voids = client.get(f"/fiscal/reports/608.txt?month={month}", headers=tokens["admin"])
    header, row = voids.text.strip().split("\n")
    assert header == f"608|{RNC}|{month.replace('-', '')}|1"
    assert row.split("|")[0] == credit.ncf and row.endswith("|04")
    assert (
        client.get("/fiscal/reports/607.txt?month=2026-13", headers=tokens["admin"]).status_code
        == 422
    )
