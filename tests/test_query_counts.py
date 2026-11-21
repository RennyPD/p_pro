"""Audit M8: list endpoints use a constant number of queries."""

from contextlib import contextmanager
from datetime import UTC, datetime

from sqlalchemy import event
from test_account_access import context, headers  # noqa: F401

from app.models import Student
from app.models.finance_model import Payment, StudentAccount
from app.models.operations_model import EarlyAlert


@contextmanager
def count_queries(sessions):
    engine = sessions.kw["bind"]
    statements = []

    def before(_conn, _cursor, statement, *_args):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", before)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", before)


def add_students(sessions, start, count):
    with sessions() as db:
        career = db.query(Student).first().career_id
        for index in range(start, start + count):
            student = Student(
                first_name="Carga",
                last_name=str(index),
                email=f"carga{index}@example.com",
                enrollment_number=f"CARGA-{index:03d}",
                telephone="8095550100",
                address="Ficticia",
                career_id=career,
            )
            db.add(student)
            db.flush()
            account = StudentAccount(student_id=student.student_id, cutoff_day=15, due_day=30)
            db.add(account)
            db.flush()
            db.add(
                Payment(
                    student_account_id=account.student_account_id,
                    amount=100,
                    reference=f"REF-{index}",
                    paid_at=datetime.now(UTC).replace(tzinfo=None),
                )
            )
            db.add(
                EarlyAlert(student_id=student.student_id, category="academic", reason="Seguimiento")
            )
        db.commit()


def queries_for(client, sessions, token, path):
    with count_queries(sessions) as statements:
        response = client.get(path, headers=token)
    assert response.status_code == 200, response.text
    return len(statements)


def test_finance_accounts_and_alerts_do_not_grow_with_rows(context):  # noqa: F811
    client, sessions = context
    admin = headers(client, "demo.admin")
    add_students(sessions, 0, 3)
    few = {
        path: queries_for(client, sessions, admin, path)
        for path in ("/finance/accounts", "/operations/alerts")
    }
    add_students(sessions, 3, 12)
    many = {path: queries_for(client, sessions, admin, path) for path in few}
    assert many == few, f"Las consultas crecen con los datos: {few} -> {many}"


# M3: los listados filtran y paginan en la base, no en memoria.
def test_directory_listings_filter_and_paginate_in_sql(context):  # noqa: F811
    client, sessions = context
    add_students(sessions, 0, 30)
    admin = headers(client, "demo.admin")

    with count_queries(sessions) as statements:
        page = client.get(
            "/students/", headers=admin, params={"q": "carga 1", "skip": 2, "limit": 3}
        )
    assert page.status_code == 200, page.text
    # "Carga 1", "Carga 10".."Carga 19": 11 matches over the combined full name.
    assert page.headers["X-Total-Count"] == "11"
    assert page.headers["X-Has-More"] == "true"
    assert len(page.json()) == 3
    listing = [s for s in statements if "FROM students" in s and "count(" not in s.lower()]
    assert listing and all("LIMIT" in s for s in listing), listing

    for path, params in (
        ("/teachers/", {"q": "zzz-nadie"}),
        ("/sections/", {"q": "PROG"}),
        ("/careers/", {"q": "a"}),
        ("/subjects/", {"q": "PROG"}),
        ("/roles/", {"q": "admin"}),
    ):
        response = client.get(path, headers=admin, params={**params, "limit": 1})
        assert response.status_code == 200, (path, response.text)
        assert "X-Total-Count" in response.headers, path
        assert len(response.json()) <= 1, path
    assert client.get("/teachers/", headers=admin, params={"q": "zzz-nadie"}).json() == []
