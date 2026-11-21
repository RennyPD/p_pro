"""Billing plans: monthly tuition generated per cycle, never twice."""

from datetime import date
from decimal import Decimal

import pytest
from db_support import make_engine
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.Session import get_db
from app.models import Charge, FinanceEvent, Student, User
from app.security import hash_password
from main import app
from scripts.seed_demo import seed_demo


@pytest.fixture
def context(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'billing.db'}", connect_args={"timeout": 15})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        seed_demo(db)
        base = db.query(Student).first()
        career_id = base.career_id
        extra = [
            # (enrollment, active, admission_date)
            ("BIL-001", True, None),
            ("BIL-002", True, None),
            ("BIL-003", False, None),  # inactive: never charged
            ("BIL-004", True, date(2026, 10, 1)),  # admitted in October
        ]
        for number, active, admitted in extra:
            db.add(
                Student(
                    first_name="Prueba",
                    last_name=number,
                    email=f"{number.lower()}@example.com",
                    enrollment_number=number,
                    telephone="8090000000",
                    address="Santo Domingo",
                    career_id=career_id,
                    active=active,
                    admission_date=admitted,
                )
            )
        db.commit()

    def override():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override
    with TestClient(app) as client:
        login = client.post(
            "/auth/login", json={"username": "demo.admin", "password": "NexoAdmin2026!"}
        )
        assert login.status_code == 200, login.text
        admin = {"Authorization": "Bearer " + login.json()["access_token"]}
        yield client, sessions, admin, career_id
    app.dependency_overrides.clear()
    engine.dispose()


def student_id(sessions, number):
    with sessions() as db:
        return db.query(Student).filter_by(enrollment_number=number).one().student_id


def create_plan(client, admin, career_id, **extra):
    body = {
        "name": "Mensualidad 2026-2027",
        "charge_description": "Mensualidad",
        "amount": "8500.00",
        "frequency": "monthly",
        "start_month": "2026-08",
        "end_month": "2026-10",
        "due_day": 5,
        "targets": {"career_ids": [career_id]},
    } | extra
    response = client.post("/finance/billing-plans", headers=admin, json=body)
    assert response.status_code == 200, response.text
    return response.json()


def plan_charges(sessions, plan_id, cycle=None):
    with sessions() as db:
        query = db.query(Charge).filter(Charge.billing_plan_id == plan_id)
        if cycle:
            query = query.filter(Charge.billing_cycle == cycle)
        return query.all()


def test_generates_each_cycle_once_for_active_students(context):
    client, sessions, admin, career_id = context
    plan = create_plan(client, admin, career_id)
    assert plan["cycles"] == ["2026-08", "2026-09", "2026-10"]
    assert plan["next_cycle"] == "2026-08"
    url = f"/finance/billing-plans/{plan['billing_plan_id']}"

    preview = client.post(url + "/preview", headers=admin, json={"cycle": "2026-08"}).json()
    # Demo student + BIL-001 + BIL-002; inactive and October admission are left out.
    assert preview["to_charge"] == 3
    assert preview["already_charged"] == 0
    assert Decimal(preview["total"]) == Decimal("25500.00")
    assert preview["due_date"] == "2026-08-05"
    assert preview["charge_description"] == "Mensualidad · agosto 2026"
    assert plan_charges(sessions, plan["billing_plan_id"]) == []  # preview writes nothing

    run = client.post(url + "/runs", headers=admin, json={"cycle": "2026-08"})
    assert run.status_code == 200, run.text
    assert run.json()["charge_count"] == 3
    again = client.post(url + "/runs", headers=admin, json={"cycle": "2026-08"})
    assert again.json()["charge_count"] == 0
    charges = plan_charges(sessions, plan["billing_plan_id"], "2026-08")
    assert len(charges) == 3
    assert {c.amount for c in charges} == {Decimal("8500.00")}
    assert {c.due_date for c in charges} == {date(2026, 8, 5)}

    account = client.get(
        f"/finance/students/{student_id(sessions, 'BIL-001')}", headers=admin
    ).json()
    assert Decimal(str(account["balance"])) == Decimal("8500.00")
    assert client.get(url.rsplit("/", 1)[0], headers=admin).json()[0]["next_cycle"] == "2026-09"

    # The student admitted in October is charged from October on.
    october = client.post(url + "/preview", headers=admin, json={"cycle": "2026-10"}).json()
    assert october["to_charge"] == 4
    with sessions() as db:
        assert db.query(FinanceEvent).filter_by(action="billing.run").count() == 2


def test_exclusions_and_individual_students(context):
    client, sessions, admin, career_id = context
    excluded, extra = student_id(sessions, "BIL-001"), student_id(sessions, "BIL-002")
    plan = create_plan(
        client,
        admin,
        career_id,
        name="Inscripción",
        frequency="single",
        targets={"career_ids": [career_id], "excluded_student_ids": [excluded]},
    )
    assert plan["cycles"] == ["2026-08"]
    url = f"/finance/billing-plans/{plan['billing_plan_id']}"
    preview = client.post(url + "/preview", headers=admin, json={"cycle": "2026-08"}).json()
    assert excluded not in {s["student_id"] for s in preview["students"]}
    assert preview["to_charge"] == 2

    only = client.put(url + "/targets", headers=admin, json={"student_ids": [extra]})
    assert only.status_code == 200, only.text
    preview = client.post(url + "/preview", headers=admin, json={"cycle": "2026-08"}).json()
    assert [s["student_id"] for s in preview["students"]] == [extra]
    conflict = client.put(
        url + "/targets",
        headers=admin,
        json={"student_ids": [extra], "excluded_student_ids": [extra]},
    )
    assert conflict.status_code == 422


def test_amount_change_only_affects_cycles_not_generated(context):
    client, sessions, admin, career_id = context
    plan = create_plan(client, admin, career_id)
    url = f"/finance/billing-plans/{plan['billing_plan_id']}"
    client.post(url + "/runs", headers=admin, json={"cycle": "2026-08"})
    changed = client.patch(url, headers=admin, json={"amount": "9000.00"})
    assert changed.status_code == 200, changed.text
    client.post(url + "/runs", headers=admin, json={"cycle": "2026-09"})
    assert {c.amount for c in plan_charges(sessions, plan["billing_plan_id"], "2026-08")} == {
        Decimal("8500.00")
    }
    assert {c.amount for c in plan_charges(sessions, plan["billing_plan_id"], "2026-09")} == {
        Decimal("9000.00")
    }
    # The end month cannot move before a generated cycle.
    assert client.patch(url, headers=admin, json={"end_month": "2026-08"}).status_code == 409


def test_rejects_cycles_outside_the_plan_and_paused_plans(context):
    client, _, admin, career_id = context
    plan = create_plan(client, admin, career_id)
    url = f"/finance/billing-plans/{plan['billing_plan_id']}"
    outside = client.post(url + "/runs", headers=admin, json={"cycle": "2026-12"})
    assert outside.status_code == 422
    assert "fuera de las fechas" in outside.json()["detail"]
    client.patch(url, headers=admin, json={"active": False})
    paused = client.post(url + "/runs", headers=admin, json={"cycle": "2026-08"})
    assert paused.status_code == 409
    bad = client.post(
        "/finance/billing-plans",
        headers=admin,
        json={
            "name": "Al revés",
            "charge_description": "Mensualidad",
            "amount": "10.00",
            "start_month": "2026-10",
            "end_month": "2026-08",
        },
    )
    assert bad.status_code == 422
    duplicate = client.post(
        "/finance/billing-plans",
        headers=admin,
        json={
            "name": "Mensualidad 2026-2027",
            "charge_description": "Otra",
            "amount": "10.00",
            "start_month": "2026-08",
        },
    )
    assert duplicate.status_code == 409


def test_idempotency_key_returns_the_same_run(context):
    client, sessions, admin, career_id = context
    plan = create_plan(client, admin, career_id)
    url = f"/finance/billing-plans/{plan['billing_plan_id']}/runs"
    body = {"cycle": "2026-08", "idempotency_key": "agosto-2026-1"}
    first = client.post(url, headers=admin, json=body).json()
    second = client.post(url, headers=admin, json=body).json()
    assert first["billing_run_id"] == second["billing_run_id"]
    assert len(plan_charges(sessions, plan["billing_plan_id"])) == 3
    other = client.post(url, headers=admin, json=body | {"cycle": "2026-09"})
    assert other.status_code == 409


def test_database_refuses_a_second_charge_for_the_same_cycle(context):
    client, sessions, admin, career_id = context
    plan = create_plan(client, admin, career_id)
    client.post(
        f"/finance/billing-plans/{plan['billing_plan_id']}/runs",
        headers=admin,
        json={"cycle": "2026-08"},
    )
    with sessions() as db:
        existing = db.query(Charge).filter_by(billing_plan_id=plan["billing_plan_id"]).first()
        db.add(
            Charge(
                student_account_id=existing.student_account_id,
                description="Duplicado",
                amount=Decimal("1.00"),
                due_date=date(2026, 8, 5),
                billing_plan_id=existing.billing_plan_id,
                billing_cycle="2026-08",
            )
        )
        with pytest.raises(IntegrityError):
            db.flush()


def test_permissions_view_versus_manage(context):
    client, sessions, admin, career_id = context
    plan = create_plan(client, admin, career_id)
    role = client.post(
        "/roles/",
        headers=admin,
        json={"name": "consulta_finanzas", "description": "Solo consulta", "scope": "institution"},
    ).json()
    client.put(
        f"/access/roles/{role['role_id']}/permissions",
        headers=admin,
        json={"permissions": ["finance.view"], "reason": "Prueba"},
    )
    with sessions() as db:
        db.add(
            User(
                username="consulta",
                email="consulta@example.com",
                password=hash_password("Prueba2026!"),
                role_id=role["role_id"],
            )
        )
        db.commit()
    viewer = {
        "Authorization": "Bearer "
        + client.post(
            "/auth/login", json={"username": "consulta", "password": "Prueba2026!"}
        ).json()["access_token"]
    }
    url = f"/finance/billing-plans/{plan['billing_plan_id']}"
    assert client.get("/finance/billing-plans", headers=viewer).status_code == 200
    assert (
        client.post(url + "/preview", headers=viewer, json={"cycle": "2026-08"}).status_code == 200
    )
    assert client.post(url + "/runs", headers=viewer, json={"cycle": "2026-08"}).status_code == 403
    assert client.patch(url, headers=viewer, json={"active": False}).status_code == 403
    assert plan_charges(sessions, plan["billing_plan_id"]) == []
