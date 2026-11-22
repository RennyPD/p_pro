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


# Paso 3: vista familiar y una transferencia para varios hijos.


@pytest.fixture
def siblings(account, bank):
    """The guardian of ``account`` also linked to a second child with two charges."""
    client, sessions, tokens, tutor, link_id, first = account
    with sessions() as db:
        guardian_id = db.query(User).filter_by(username="tutor.01").one().guardian_id
        second = Student(
            first_name="Mateo",
            last_name="Hermano",
            email="mateo.hermano@example.com",
            enrollment_number="HERM-2",
            telephone="8095550100",
            address="Calle 2",
            career_id=db.get(Student, first).career_id,
        )
        db.add(second)
        db.commit()
        second_id = second.student_id
    linked = client.post(
        "/community/guardian-links",
        headers=tokens["admin"],
        json={"student_id": second_id, "guardian_id": guardian_id, "relationship": "Padre"},
    )
    assert linked.status_code == 200, linked.text
    # First child owes 1,500 (500 overdue since 5 days, 1,000 in 25 days).
    add_charges(sessions, second_id, ("800.00", -20), ("400.00", 10))
    return client, sessions, tokens, tutor, first, second_id


def test_family_finance_totals_per_child_and_concept(siblings):
    client, _, _, tutor, first, second = siblings
    response = client.get("/guardian/finance", headers=tutor)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_balance"] == 2700.0
    assert body["total_overdue"] == 1300.0
    assert {s["student_id"]: s["balance"] for s in body["students"]} == {
        first: 1500.0,
        second: 1200.0,
    }
    assert sum(c["remaining"] for c in body["concepts"]) == body["total_balance"]


def test_allocation_pays_what_is_due_first_across_children(siblings):
    client, _, _, tutor, first, second = siblings
    # Oldest first: second's 800 (20 days late), first's 500 (5 days late), then 400 of second.
    suggestion = client.get("/guardian/finance/allocation", headers=tutor, params={"amount": 1500})
    assert suggestion.status_code == 200, suggestion.text
    assert {a["student_id"]: a["amount"] for a in suggestion.json()} == {
        first: 500.0,
        second: 1000.0,
    }
    too_much = client.get("/guardian/finance/allocation", headers=tutor, params={"amount": 5000})
    assert too_much.status_code == 422


def family_transfer(client, tutor, allocations, reference="LOTE-FAM-1"):
    return client.post(
        "/guardian/transfers",
        headers=tutor,
        json={
            "reference": reference,
            "bank": "Banco Ficticio",
            "proof_base64": PNG,
            "allocations": allocations,
        },
    )


def test_one_transfer_for_two_children_is_approved_as_a_whole(siblings):
    client, sessions, tokens, tutor, first, second = siblings
    sent = family_transfer(
        client,
        tutor,
        [{"student_id": first, "amount": "500.00"}, {"student_id": second, "amount": "800.00"}],
    )
    assert sent.status_code == 200, sent.text
    batch = sent.json()
    assert batch["total"] == 1300.0 and batch["status"] == "pending"
    assert [s["status"] for s in batch["shares"]] == ["pending", "pending"]
    assert client.get("/guardian/transfers", headers=tutor).json()[0]["reference"] == "LOTE-FAM-1"

    inbox = client.get("/finance/transfers", headers=tokens["admin"]).json()
    grouped = [t for t in inbox if t["batch_id"] == batch["transfer_batch_id"]]
    assert len(grouped) == 2 and all(t["batch_total"] == 1300.0 for t in grouped)
    assert {t["reference"] for t in grouped} == {"LOTE-FAM-1 (1/2)", "LOTE-FAM-1 (2/2)"}
    proof = client.get(
        f"/finance/transfers/{grouped[0]['transfer_request_id']}/proof", headers=tutor
    )
    assert proof.status_code == 200

    approved = client.post(
        f"/finance/transfers/{grouped[0]['transfer_request_id']}/review",
        headers=tokens["admin"],
        json={"approve": True, "reason": "Depósito verificado"},
    )
    assert approved.status_code == 200, approved.text
    after = client.get("/guardian/transfers", headers=tutor).json()[0]
    assert after["status"] == "approved"
    assert [s["status"] for s in after["shares"]] == ["approved", "approved"]
    totals = client.get("/guardian/finance", headers=tutor).json()
    assert totals["total_balance"] == 1400.0
    for student in (first, second):
        payments = client.get(f"/guardian/students/{student}/statement", headers=tutor).json()[
            "payments"
        ]
        assert payments[0]["receipt_number"].startswith("REC-")


def test_rejecting_a_family_transfer_rejects_every_share(siblings):
    client, _, tokens, tutor, first, second = siblings
    sent = family_transfer(
        client,
        tutor,
        [{"student_id": first, "amount": "100.00"}, {"student_id": second, "amount": "100.00"}],
        reference="LOTE-RECHAZO",
    )
    share = sent.json()["shares"][1]["transfer_request_id"]
    rejected = client.post(
        f"/finance/transfers/{share}/review",
        headers=tokens["admin"],
        json={"approve": False, "reason": "No aparece en el banco"},
    )
    assert rejected.status_code == 200, rejected.text
    batch = client.get("/guardian/transfers", headers=tutor).json()[0]
    assert batch["status"] == "rejected" and batch["review_reason"] == "No aparece en el banco"
    assert client.get("/guardian/finance", headers=tutor).json()["total_balance"] == 2700.0


def test_family_transfer_validates_links_amounts_and_references(siblings):
    client, sessions, tokens, tutor, first, second = siblings
    with sessions() as db:
        stranger = Student(
            first_name="Ajeno",
            last_name="Familia",
            email="ajeno.familia@example.com",
            enrollment_number="AJF-1",
            telephone="8095550100",
            address="Calle 3",
            career_id=db.get(Student, first).career_id,
        )
        db.add(stranger)
        db.commit()
        stranger_id = stranger.student_id
    foreign = family_transfer(client, tutor, [{"student_id": stranger_id, "amount": "10.00"}])
    assert foreign.status_code == 403
    excessive = family_transfer(client, tutor, [{"student_id": second, "amount": "5000.00"}])
    assert excessive.status_code == 422
    repeated = family_transfer(
        client,
        tutor,
        [{"student_id": first, "amount": "10.00"}, {"student_id": first, "amount": "10.00"}],
    )
    assert repeated.status_code == 422
    assert (
        family_transfer(client, tutor, [{"student_id": first, "amount": "10.00"}]).status_code
        == 200
    )
    reused = report(client, tutor, first, "10.00", "LOTE-FAM-1")
    assert reused.status_code == 409
    again = family_transfer(client, tutor, [{"student_id": second, "amount": "10.00"}])
    assert again.status_code == 409
