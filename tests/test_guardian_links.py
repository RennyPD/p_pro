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


# Paso 2: detalle por hijo.

AREAS = {
    "attendance": "can_view_attendance",
    "grades": "can_view_academic",
    "performance": "can_view_academic",
    "tasks": "can_view_tasks",
    "finance": "can_view_finance",
}


def test_guardian_detail_endpoints_return_the_linked_student(family):
    from app.models import Enrollment, Grade

    client, sessions, _, tutor, _, student_id = family
    base = f"/guardian/students/{student_id}"

    attendance = client.get(f"{base}/attendance", headers=tutor)
    assert attendance.status_code == 200, attendance.text
    body = attendance.json()
    assert body["student_id"] == student_id
    assert body["total_count"] == sum(c["total_count"] for c in body["courses"])
    assert set(body["counts"]) >= {"present", "absent", "late", "excused"}

    grades = client.get(f"{base}/grades", headers=tutor)
    assert grades.status_code == 200, grades.text
    shown = {
        a["grade_value"]
        for course in grades.json()["courses"]
        for a in course["assessments"]
        if a["grade_value"] is not None
    }
    with sessions() as db:
        drafts = {
            g.grade_value
            for g in db.query(Grade).join(Enrollment).filter(Enrollment.student_id == student_id)
            if g.status != "published"
        }
        published = {
            g.grade_value
            for g in db.query(Grade).join(Enrollment).filter(Enrollment.student_id == student_id)
            if g.status == "published"
        }
    assert shown <= published
    assert not (shown & (drafts - published))

    tasks = client.get(f"{base}/tasks", headers=tutor, params={"limit": 2})
    assert tasks.status_code == 200, tasks.text
    assert "X-Total-Count" in tasks.headers and len(tasks.json()) <= 2
    assert all(t["status"] in {"pending", "overdue", "submitted", "graded"} for t in tasks.json())
    for status in ("pending", "overdue", "submitted", "graded"):
        filtered = client.get(f"{base}/tasks", headers=tutor, params={"status": status})
        assert all(t["status"] == status for t in filtered.json()), status

    finance = client.get(f"{base}/finance", headers=tutor)
    assert finance.status_code == 200, finance.text
    assert finance.json()["financial_responsible"] is False
    assert "next_due_date" in finance.json()

    performance = client.get(f"{base}/performance", headers=tutor)
    assert performance.status_code == 200, performance.text
    assert all("average_grade" in item for item in performance.json()["periods"])


@pytest.mark.parametrize("endpoint", sorted(AREAS))
def test_each_area_can_be_restricted_on_its_own(family, endpoint):
    client, _, tokens, tutor, link_id, student_id = family
    column = AREAS[endpoint]
    saved = client.patch(
        f"/community/guardian-links/{link_id}", headers=tokens["admin"], json={column: False}
    )
    assert saved.status_code == 200, saved.text
    for other, other_column in AREAS.items():
        response = client.get(f"/guardian/students/{student_id}/{other}", headers=tutor)
        expected = 403 if other_column == column else 200
        assert response.status_code == expected, (other, response.text)


def test_guardian_detail_is_limited_to_linked_students_and_guardian_accounts(family):
    from app.models import Student

    client, sessions, tokens, tutor, _, student_id = family
    with sessions() as db:
        other = Student(
            first_name="Ajeno",
            last_name="Vínculo",
            email="ajeno@example.com",
            enrollment_number="AJENO-1",
            telephone="8095550100",
            address="Calle 9",
            career_id=db.get(Student, student_id).career_id,
        )
        db.add(other)
        db.commit()
        other_id = other.student_id
    for area in AREAS:
        denied = client.get(f"/guardian/students/{other_id}/{area}", headers=tutor)
        assert denied.status_code == 403, area
        staff = client.get(f"/guardian/students/{student_id}/{area}", headers=tokens["admin"])
        assert staff.status_code == 403, area
        own = client.get(f"/guardian/students/{student_id}/{area}", headers=tokens["estudiante"])
        assert own.status_code == 403, area
