"""School finance: grade plans, sibling discount, late fees, holds, roles, reports (Fase 3 E)."""

from datetime import date
from decimal import Decimal

import pytest
from test_class_groups import create_group, school  # noqa: F401  (shared fixtures)
from test_write_audit import demo, entries  # noqa: F401

from app.models import (
    BillingRun,
    Charge,
    FinancialAdjustment,
    Guardian,
    Role,
    RolePermission,
    Student,
    StudentAccount,
    StudentGuardian,
    User,
)
from app.models.finance_model import FinancePolicy
from app.security import hash_password
from app.services import finance_automation as automation
from app.services.permission_catalog import ensure_catalog


def policy_payload(**changes):
    return {
        "late_fee_enabled": False,
        "grace_days": 5,
        "late_fee_kind": "percent",
        "late_fee_value": "5",
        "hold_enabled": False,
        "hold_after_days": 30,
        "hold_min_amount": "0",
        "sibling_discount_enabled": False,
        "sibling_second_percent": "10",
        "sibling_third_percent": "15",
        "auto_billing_enabled": False,
        "billing_lead_days": 10,
        "reason": "Política del año",
        **changes,
    }


def link_family(db, student_ids, email="familia@nexo-academico.com"):
    guardian = Guardian(first_name="Rosa", last_name="Peña", email=email, telephone="809-555-0000")
    db.add(guardian)
    db.flush()
    for student_id in student_ids:
        db.add(
            StudentGuardian(
                student_id=student_id,
                guardian_id=guardian.guardian_id,
                relationship="Madre",
                financial_responsible=True,
            )
        )
    db.commit()
    return guardian.guardian_id


@pytest.fixture
def grade_plan(school):  # noqa: F811
    """1.º A with the three students, and a monthly tuition plan for grade 1."""
    client, sessions, tokens, ids = school
    admin = tokens["admin"]
    gid = create_group(client, admin, ids)["class_group_id"]
    for student_id in ids["students"]:
        added = client.post(
            f"/class-groups/{gid}/members", headers=admin, json={"student_id": student_id}
        )
        assert added.status_code == 200, added.text
    plan = client.post(
        "/finance/billing-plans",
        headers=admin,
        json={
            "name": "Mensualidad 1.º",
            "charge_description": "Mensualidad",
            "amount": "5000",
            "school_year_id": ids["years"][0],
            "sibling_discount": True,
            "targets": {"grades": [{"career_id": ids["career"], "grade_number": 1}]},
        },
    )
    assert plan.status_code == 200, plan.text
    return client, sessions, tokens, ids, plan.json()


def test_grade_plan_uses_the_year_months_and_the_groups(grade_plan):
    client, sessions, tokens, ids, plan = grade_plan
    assert plan["start_month"] == "2026-08" and plan["end_month"] == "2027-06"
    assert plan["targets"]["grades"] == [{"career_id": ids["career"], "grade_number": 1}]
    preview = client.post(
        f"/finance/billing-plans/{plan['billing_plan_id']}/preview",
        headers=tokens["admin"],
        json={"cycle": "2026-09"},
    )
    assert preview.status_code == 200, preview.text
    # The held student is not in the group: only the three members are billed.
    assert preview.json()["to_charge"] == 3
    without_year = client.post(
        "/finance/billing-plans",
        headers=tokens["admin"],
        json={
            "name": "Sin año",
            "charge_description": "Mensualidad",
            "amount": "100",
            "start_month": "2026-09",
            "targets": {"grades": [{"career_id": ids["career"], "grade_number": 1}]},
        },
    )
    assert without_year.status_code == 422


def test_sibling_discount_goes_to_the_younger_children_once(grade_plan):
    client, sessions, tokens, ids, plan = grade_plan
    admin = tokens["admin"]
    with sessions() as db:
        link_family(db, ids["students"][:2])
    assert (
        client.put(
            "/finance/policy", headers=tokens["estudiante"], json=policy_payload()
        ).status_code
        == 403
    )
    enabled = client.put(
        "/finance/policy", headers=admin, json=policy_payload(sibling_discount_enabled=True)
    )
    assert enabled.status_code == 200, enabled.text
    body = {"cycle": "2026-09", "reason": "Mensualidad de septiembre"}
    run = client.post(
        f"/finance/billing-plans/{plan['billing_plan_id']}/runs", headers=admin, json=body
    )
    assert run.status_code == 200, run.text
    with sessions() as db:
        discounts = db.query(FinancialAdjustment).filter_by(kind="discount").all()
        assert len(discounts) == 1
        assert discounts[0].amount == Decimal("500.00")
        assert discounts[0].automation_key.startswith("sibling:")
        discounted = db.get(Charge, discounts[0].charge_id)
        account = db.get(StudentAccount, discounted.student_account_id)
        assert account.student_id == ids["students"][1]
        # Running the family again posts nothing twice.
        assert automation.apply_sibling_discounts(db, "2026-09", set(ids["students"])) == 0
    assert entries(sessions, "finance.policy_updated", "finance-policy")


def test_late_fee_hold_and_automatic_lift(grade_plan):
    client, sessions, tokens, ids, plan = grade_plan
    admin = tokens["admin"]
    client.put(
        "/finance/policy",
        headers=admin,
        json=policy_payload(
            late_fee_enabled=True, hold_enabled=True, hold_after_days=30, hold_min_amount="1000"
        ),
    )
    client.post(
        f"/finance/billing-plans/{plan['billing_plan_id']}/runs",
        headers=admin,
        json={"cycle": "2026-08", "reason": "Agosto"},
    )
    first, second, third = ids["students"]
    with sessions() as db:
        manual = db.get(Student, third)
        manual.financial_hold, manual.financial_hold_source = True, "manual"
        db.commit()
    # Due 2026-08-05: on 08-08 still in grace; on 09-10, 36 days late.
    with sessions() as db:
        early = automation.run_daily(db, date(2026, 8, 8))
        assert early.late_fees == [] and early.holds_set == []
        db.commit()
    with sessions() as db:
        result = automation.run_daily(db, date(2026, 9, 10))
        db.commit()
        assert len(result.late_fees) == 3 and result.late_fees[0]["amount"] == "250.00"
        assert sorted(result.holds_set) == ["Alumno 001", "Alumno 002"]
    with sessions() as db:
        again = automation.run_daily(db, date(2026, 9, 11))
        db.commit()
        assert again.late_fees == [] and again.holds_set == []
        assert db.get(Student, first).financial_hold_source == "auto"
    # Paying the whole balance lifts the automatic hold right away.
    statement = client.get(f"/finance/students/{first}/statement", headers=admin).json()
    paid = client.post(
        f"/finance/students/{first}/payments",
        headers=admin,
        json={"amount": str(statement["balance"]), "reference": "CAJA-0001"},
    )
    assert paid.status_code == 200, paid.text
    with sessions() as db:
        assert db.get(Student, first).financial_hold is False
        # A manual hold is never lifted by the job.
        automation.run_daily(db, date(2026, 9, 12))
        db.commit()
        assert db.get(Student, third).financial_hold is True
    assert entries(sessions, "student.financial_hold.auto_set")
    assert entries(sessions, "student.financial_hold.auto_lifted")


def test_scheduled_billing_and_simulation(grade_plan):
    client, sessions, tokens, ids, plan = grade_plan
    admin = tokens["admin"]
    client.put(
        "/finance/policy",
        headers=admin,
        json=policy_payload(auto_billing_enabled=True, billing_lead_days=10),
    )
    simulated = client.post("/finance/automation/simulate?day=2026-08-01", headers=admin)
    assert simulated.status_code == 200, simulated.text
    assert [r["cycle"] for r in simulated.json()["billing_runs"]] == ["2026-08"]
    with sessions() as db:
        assert db.query(BillingRun).count() == 0  # the simulation saved nothing
        result = automation.run_daily(db, date(2026, 8, 27))
        db.commit()
        # August (due 08-05) and September (due 09-05, within 10 days) are generated.
        assert [r["cycle"] for r in result.billing_runs] == ["2026-08", "2026-09"]
        assert all(run.created_by is None for run in db.query(BillingRun))
        assert automation.run_daily(db, date(2026, 8, 28)).billing_runs == []


def make_cashier(sessions):
    with sessions() as db:
        catalog = ensure_catalog(db)
        role = Role(name="caja", label="Caja", description="Cobros")
        db.add(role)
        db.flush()
        for slug in ("finance.view", "finance.collect"):
            db.add(RolePermission(role_id=role.role_id, permission_id=catalog[slug].permission_id))
        db.add(
            User(
                username="cajera",
                email="cajera@nexo-academico.com",
                password=hash_password("NexoCajera2026!"),
                role_id=role.role_id,
            )
        )
        db.commit()


def test_cashier_collects_but_does_not_supervise(demo):  # noqa: F811
    client, sessions, tokens = demo
    admin = tokens["admin"]
    make_cashier(sessions)
    login = client.post("/auth/login", json={"username": "cajera", "password": "NexoCajera2026!"})
    cashier = {"Authorization": "Bearer " + login.json()["access_token"]}
    with sessions() as db:
        student = db.query(User).filter_by(username="demo.estudiante").one().student_id
    base = f"/finance/students/{student}"
    charge = client.post(
        base + "/charges",
        headers=admin,
        json={"description": "Inscripción", "amount": "3000", "due_date": "2026-11-30"},
    )
    assert charge.status_code == 200, charge.text
    assert (
        client.post(
            base + "/charges",
            headers=cashier,
            json={"description": "Otro", "amount": "10", "due_date": "2026-11-30"},
        ).status_code
        == 403
    )
    paid = client.post(
        base + "/payments", headers=cashier, json={"amount": "1000", "reference": "CAJA-777"}
    )
    assert paid.status_code == 200, paid.text
    payment = next(t for t in paid.json()["transactions"] if t["type"] == "payment")
    reverse = f"{base}/transactions/payment/{payment['transaction_id']}/reverse"
    assert client.post(reverse, headers=cashier, json={"reason": "Error"}).status_code == 403
    mine = client.get("/finance/cashier/today", headers=cashier).json()
    assert mine["payments"] == 1 and mine["total"] == 1000
    # A supervisor who did not post the payment can reverse it.
    assert client.post(reverse, headers=admin, json={"reason": "Error de caja"}).status_code == 200


def test_reports_aging_income_expected(grade_plan):
    client, sessions, tokens, ids, plan = grade_plan
    admin = tokens["admin"]
    with sessions() as db:
        link_family(db, ids["students"][:2])
    client.post(
        f"/finance/billing-plans/{plan['billing_plan_id']}/runs",
        headers=admin,
        json={"cycle": "2026-08", "reason": "Agosto"},
    )
    summary = client.get("/finance/reports/aging", headers=admin)
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["students_overdue"] == 3
    assert body["totals"]["d90_plus"] == 15000  # due 2026-08-05, today is later
    assert body["groups"][0]["label"] == "1.º A · Secundaria"
    accounts = client.get("/finance/reports/aging/accounts?limit=2", headers=admin)
    assert accounts.headers["X-Total-Count"] == "3" and len(accounts.json()) == 2
    assert accounts.json()[0]["family"].startswith("Familia Rosa Peña")
    csv = client.get("/finance/reports/aging/accounts.csv", headers=admin)
    assert csv.status_code == 200 and "Matrícula" in csv.text and "ESC-001" in csv.text
    first = ids["students"][0]
    client.post(
        f"/finance/students/{first}/payments",
        headers=admin,
        json={"amount": "1500", "reference": "CAJA-0101"},
    )
    today = date.today().isoformat()
    income = client.get(
        f"/finance/reports/income?start=2026-01-01&end={today}&group_by=method", headers=admin
    ).json()
    assert income["payments"] == 1 and income["rows"][0]["label"] == "Efectivo"
    expected = client.get("/finance/reports/expected?year=2026", headers=admin).json()
    august = next(m for m in expected if m["month"] == "2026-08")
    assert august["expected"] == 15000 and august["by_concept"] == {"Mensualidad": 15000.0}
    family = client.get(f"/finance/students/{first}/family", headers=admin).json()
    assert family["responsible"] == ["Rosa Peña"] and len(family["members"]) == 2
    assert family["balance"] == 8500
    pdf = client.get(f"/finance/students/{first}/family.pdf", headers=admin)
    assert pdf.headers["content-type"] == "application/pdf"
    assert client.get("/finance/reports/aging", headers=tokens["estudiante"]).status_code == 403
    with sessions() as db:
        assert db.query(FinancePolicy).count() == 0  # reading never creates the policy
