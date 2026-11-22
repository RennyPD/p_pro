"""Payments module for students and guardians (Fase 2, paso 4; M7, M8)."""

from datetime import timedelta
from decimal import Decimal

import pytest
from test_guardian_links import family  # noqa: F401  (shared fixtures)
from test_write_audit import demo, entries  # noqa: F401

from app.models import Student, User
from app.models.finance_model import Charge, StudentAccount
from app.services.business_time import business_date


def add_charges(sessions, student_id, *items):
    """Charges (amount, days from today) on the student's account."""
    with sessions() as db:
        account = db.query(StudentAccount).filter_by(student_id=student_id).first()
        if account is None:
            account = StudentAccount(student_id=student_id, cutoff_day=15, due_day=30)
            db.add(account)
            db.flush()
        for index, (amount, days) in enumerate(items):
            db.add(
                Charge(
                    student_account_id=account.student_account_id,
                    description=f"Cuota {index + 1}",
                    amount=Decimal(amount),
                    due_date=business_date() + timedelta(days=days),
                )
            )
        db.commit()


def pay(client, headers, student_id, amount, reference):
    response = client.post(
        f"/finance/students/{student_id}/payments",
        headers=headers,
        json={"amount": amount, "reference": reference, "method": "cash"},
    )
    assert response.status_code == 200, response.text


@pytest.fixture
def account(family):  # noqa: F811
    client, sessions, tokens, tutor, link_id, student_id = family
    with sessions() as db:
        account = db.query(StudentAccount).filter_by(student_id=student_id).first()
        if account is not None:
            for item in account.charges + account.payments + account.adjustments:
                db.delete(item)
            db.commit()
    add_charges(sessions, student_id, ("1000.00", -40), ("1000.00", -5), ("1000.00", 25))
    pay(client, tokens["admin"], student_id, "1500.00", "PAGO-EST-1")
    return family


# Paso 1: estado de cuenta.


def test_statement_allocates_payments_oldest_first_and_matches_the_balance(account):
    client, _, tokens, tutor, _, student_id = account
    statement = client.get(f"/finance/students/{student_id}/statement", headers=tokens["admin"])
    assert statement.status_code == 200, statement.text
    body = statement.json()
    assert [o["status"] for o in body["obligations"]] == ["paid", "overdue", "pending"]
    assert [o["paid_amount"] for o in body["obligations"]] == [1000.0, 500.0, 0.0]
    assert body["balance"] == 1500.0
    assert body["balance"] == sum(o["remaining"] for o in body["obligations"])
    assert body["overdue_balance"] == sum(
        o["remaining"] for o in body["obligations"] if o["status"] == "overdue"
    )
    assert body["next_due_amount"] == 1000.0
    assert body["payments"][0]["receipt_number"].startswith("REC-")
    assert sum(c["remaining"] for c in body["concepts"]) == body["balance"]

    summary = client.get(f"/finance/students/{student_id}", headers=tokens["admin"]).json()
    assert summary["overdue_balance"] == body["overdue_balance"]

    guardian = client.get(f"/guardian/students/{student_id}/statement", headers=tutor)
    assert guardian.status_code == 200, guardian.text
    assert guardian.json()["obligations"] == body["obligations"]


def test_statement_respects_guardian_access_and_the_institution_setting(account):
    client, sessions, tokens, tutor, link_id, student_id = account
    client.patch(
        f"/community/guardian-links/{link_id}",
        headers=tokens["admin"],
        json={"can_view_finance": False},
    )
    assert (
        client.get(f"/guardian/students/{student_id}/statement", headers=tutor).status_code == 403
    )

    with sessions() as db:
        own = db.query(User).filter_by(username="demo.estudiante").one().student_id
    path = f"/finance/students/{own}/statement"
    assert client.get(path, headers=tokens["estudiante"]).status_code == 200
    with sessions() as db:
        other = db.query(Student).filter(Student.student_id != own).first()
    if other is not None:
        foreign = f"/finance/students/{other.student_id}/statement"
        assert client.get(foreign, headers=tokens["estudiante"]).status_code == 403


# Paso 2: el tutor reporta pagos y descarga recibos.

PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="


@pytest.fixture
def bank(monkeypatch):
    from app.db.database import settings

    monkeypatch.setattr(settings, "finance_transfer_instructions", "Cuenta ficticia de pruebas")


def report(client, headers, student_id, amount, reference):
    return client.post(
        f"/finance/students/{student_id}/transfers",
        headers=headers,
        json={
            "amount": amount,
            "reference": reference,
            "bank": "Banco Ficticio",
            "proof_base64": PNG,
        },
    )


def test_guardian_reports_a_transfer_and_downloads_receipts(account, bank):
    client, sessions, tokens, tutor, _, student_id = account
    sent = report(client, tutor, student_id, "500.00", "TRF-TUTOR-1")
    assert sent.status_code == 200, sent.text
    listed = client.get(f"/finance/students/{student_id}/transfers", headers=tutor)
    assert [t["reference"] for t in listed.json()] == ["TRF-TUTOR-1"]
    request_id = sent.json()["transfer_request_id"]
    assert client.get(f"/finance/transfers/{request_id}/proof", headers=tutor).status_code == 200

    reviewed = client.post(
        f"/finance/transfers/{request_id}/review",
        headers=tokens["admin"],
        json={"approve": True, "reason": "Depósito verificado"},
    )
    assert reviewed.status_code == 200, reviewed.text
    statement = client.get(f"/guardian/students/{student_id}/statement", headers=tutor).json()
    assert statement["balance"] == 1000.0
    receipt = client.get(
        f"/finance/payments/{statement['payments'][0]['payment_id']}/receipt.pdf", headers=tutor
    )
    assert receipt.status_code == 200
    assert receipt.headers["content-type"] == "application/pdf"


def test_guardian_without_finance_access_or_link_cannot_report(account, bank):
    client, sessions, tokens, tutor, link_id, student_id = account
    with sessions() as db:
        other = Student(
            first_name="Sin",
            last_name="Vínculo",
            email="sin.vinculo@example.com",
            enrollment_number="SINV-1",
            telephone="8095550100",
            address="Calle 1",
            career_id=db.get(Student, student_id).career_id,
        )
        db.add(other)
        db.commit()
        other_id = other.student_id
    assert report(client, tutor, other_id, "10.00", "TRF-AJENO").status_code == 403
    client.patch(
        f"/community/guardian-links/{link_id}",
        headers=tokens["admin"],
        json={"can_view_finance": False},
    )
    assert report(client, tutor, student_id, "10.00", "TRF-SIN-ACCESO").status_code == 403
    listed = client.get(f"/finance/students/{student_id}/transfers", headers=tutor)
    assert listed.status_code == 403
