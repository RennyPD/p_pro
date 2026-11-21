"""Guardian–student links with per-area permissions (audit A1).

By default a guardian sees attendance, grades, balance, tasks and performance of
every linked student (product decision of 21/11/2026). The institution can
restrict an area on a single link; every change is locked and audited.
"""

import pytest
from test_write_audit import demo, entries  # noqa: F401  (shared fixture)

from app.models import StudentGuardian, User
from scripts.seed_guardian_portal import seed_guardians


@pytest.fixture
def family(demo):  # noqa: F811
    client, sessions, tokens = demo
    with sessions() as db:
        assert seed_guardians(db, limit=1) == 1
        guardian = db.query(User).filter_by(username="tutor.01").one()
        link = db.query(StudentGuardian).filter_by(guardian_id=guardian.guardian_id).one()
        link_id, student_id = link.student_guardian_id, link.student_id
    response = client.post(
        "/auth/login", json={"username": "tutor.01", "password": "NexoTutor2026!"}
    )
    assert response.status_code == 200, response.text
    tutor = {"Authorization": "Bearer " + response.json()["access_token"]}
    return client, sessions, tokens, tutor, link_id, student_id


def overview(client, tutor):
    response = client.get("/operations/guardian/overview", headers=tutor)
    assert response.status_code == 200, response.text
    [student] = response.json()
    return student


def test_guardian_sees_everything_by_default(family):
    client, _, tokens, tutor, _, student_id = family
    # Regression: seeding the first guardian role created the permission catalog
    # and silently left the built-in administrator without its default grants.
    admin_access = client.get("/access/me", headers=tokens["admin"]).json()
    assert "students.manage" in admin_access["permissions"]
    student = overview(client, tutor)
    assert student["permissions"] == {
        "academic": True,
        "attendance": True,
        "finance": True,
        "tasks": True,
    }
    assert student["balance"] is not None
    assert (
        client.get(f"/documents/students/{student_id}/statement.pdf", headers=tutor).status_code
        == 200
    )
    links = client.get(f"/community/students/{student_id}/guardians", headers=tokens["admin"])
    assert links.json()[0]["can_view_finance"] is True
    assert links.json()[0]["financial_responsible"] is False


def test_restricting_a_link_hides_that_area_everywhere(family):
    client, sessions, tokens, tutor, link_id, student_id = family
    restricted = client.patch(
        f"/community/guardian-links/{link_id}",
        headers=tokens["admin"],
        json={"can_view_finance": False, "can_view_academic": False},
    )
    assert restricted.status_code == 200, restricted.text
    assert restricted.json()["can_view_finance"] is False

    student = overview(client, tutor)
    assert student["permissions"]["finance"] is False
    assert student["balance"] is None
    assert student["average_grade"] is None and student["schedule"] == []
    assert student["permissions"]["attendance"] is True
    statement = client.get(f"/documents/students/{student_id}/statement.pdf", headers=tutor)
    assert statement.status_code == 403
    report = client.get(f"/documents/students/{student_id}/report-card.pdf", headers=tutor)
    assert report.status_code == 403

    [(actor, resource, detail)] = entries(sessions, "guardian.link.updated")
    assert (actor, resource) == ("demo.admin", f"student:{student_id}")
    assert "can_view_finance: sí → no" in detail and "can_view_academic: sí → no" in detail


def test_link_changes_need_students_manage_and_unlinking_removes_access(family):
    client, sessions, tokens, tutor, link_id, student_id = family
    path = f"/community/guardian-links/{link_id}"
    assert client.patch(path, headers=tutor, json={"can_view_finance": True}).status_code == 403
    assert (
        client.patch(path, headers=tokens["docente"], json={"can_view_finance": False}).status_code
        == 403
    )
    assert (
        client.patch(path, headers=tokens["admin"], json={"relationship": None}).status_code == 422
    )
    assert (
        client.patch(
            "/community/guardian-links/99999", headers=tokens["admin"], json={}
        ).status_code
        == 404
    )

    assert client.delete(path, headers=tokens["admin"]).status_code == 200
    assert client.get("/operations/guardian/overview", headers=tutor).json() == []
    assert (
        client.get(f"/documents/students/{student_id}/report-card.pdf", headers=tutor).status_code
        == 403
    )
    assert entries(sessions, "guardian.unlinked")[0][0] == "demo.admin"
