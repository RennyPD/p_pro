"""Support tickets between institutions and Nexo's team (Fase 5, step G6)."""

from datetime import datetime

import pytest
from test_billing import set_subscription
from test_platform import platform_admin, platform_login
from test_write_audit import demo, entries  # noqa: F401  (shared fixtures)

from app.db.database import settings
from app.models import EmailOutbox, PlatformAuditLog, User

TICKET = {
    "subject": "No veo la sección de 3.º B",
    "category": "uso",
    "priority": "alta",
    "body": "Desde ayer no aparece la sección en Mis secciones.",
}


@pytest.fixture
def desk(demo, monkeypatch):  # noqa: F811
    client, sessions, tokens = demo
    monkeypatch.setattr(settings, "support_email", "soporte@nexo.com.do")
    monkeypatch.setattr(settings, "app_url", "https://nexo.example.edu")
    return client, sessions, tokens


def emails(sessions, to):
    with sessions() as db:
        return [row.subject for row in db.query(EmailOutbox).filter_by(to_address=to)]


def test_an_account_opens_a_ticket_and_its_administration_sees_it(desk):
    client, sessions, tokens = desk
    opened = client.post("/support/tickets", headers=tokens["docente"], json=TICKET)
    assert opened.status_code == 200, opened.text
    ticket = opened.json()
    assert ticket["status"] == "open" and ticket["messages"][0]["author_kind"] == "institution"
    assert any("[Soporte #" in subject for subject in emails(sessions, "soporte@nexo.com.do"))
    assert entries(sessions, "support.opened")
    mine = client.get("/support/tickets", headers=tokens["docente"])
    assert mine.headers["X-Total-Count"] == "1"
    admin = client.get("/support/tickets", headers=tokens["admin"]).json()
    assert [row["support_ticket_id"] for row in admin] == [ticket["support_ticket_id"]]
    other = client.get(
        f"/support/tickets/{ticket['support_ticket_id']}", headers=tokens["estudiante"]
    )
    assert other.status_code == 404
    bad = client.post("/support/tickets", headers=tokens["docente"], json={**TICKET, "body": "x"})
    assert bad.status_code == 422


def test_the_team_answers_from_the_platform_and_the_requester_is_emailed(desk):
    client, sessions, tokens = desk
    ticket_id = client.post("/support/tickets", headers=tokens["docente"], json=TICKET).json()[
        "support_ticket_id"
    ]
    platform = platform_login(client, platform_admin(sessions))
    inbox = client.get("/platform/support?status=open", headers=platform).json()
    assert inbox[0]["support_ticket_id"] == ticket_id and inbox[0]["institution"]
    assert client.get("/platform/support", headers=tokens["admin"]).status_code == 403
    answered = client.post(
        f"/platform/support/{ticket_id}/reply",
        headers=platform,
        json={"body": "La sección estaba en otro período. Ya la verás.", "status": "waiting"},
    )
    assert answered.status_code == 200, answered.text
    assert answered.json()["messages"][-1]["author_kind"] == "platform"
    with sessions() as db:
        teacher_email = db.query(User).filter_by(username="demo.docente").one().email
        assert db.query(PlatformAuditLog).filter_by(action="support.answered").count() == 1
    assert any("Respuesta a tu ticket" in s for s in emails(sessions, teacher_email))
    # The institution answers back: the ticket returns to the team.
    back = client.post(
        f"/support/tickets/{ticket_id}/messages",
        headers=tokens["docente"],
        json={"body": "¡Gracias, ya aparece!"},
    )
    assert back.json()["status"] == "open" and len(back.json()["messages"]) == 3
    client.post(f"/platform/support/{ticket_id}/reply", headers=platform, json={"status": "closed"})
    closed = client.post(
        f"/support/tickets/{ticket_id}/messages",
        headers=tokens["docente"],
        json={"body": "Otra cosa"},
    )
    assert closed.status_code == 409


def test_unpaid_institutions_can_still_ask_for_help(desk):
    client, sessions, tokens = desk
    set_subscription(sessions, status="read_only", read_only_since=datetime.now())
    assert client.post("/support/tickets", headers=tokens["admin"], json=TICKET).status_code == 200
