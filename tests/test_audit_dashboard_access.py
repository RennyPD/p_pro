"""Coverage for the audit log, the dashboard and the role permission editor (audit B3)."""

from datetime import date, timedelta

from test_write_audit import a_student, demo  # noqa: F401  (shared fixture)

from app.models import AcademicPeriod, Role, User


def role_id(sessions, name):
    with sessions() as db:
        return db.query(Role).filter_by(name=name).one().role_id


# Auditoría.


def test_audit_log_filters_hides_secrets_and_requires_audit_view(demo):  # noqa: F811
    client, sessions, tokens = demo
    admin = tokens["admin"]
    student_id, _ = a_student(sessions)
    changed = client.patch(f"/students/{student_id}", headers=admin, json={"academic_hold": True})
    assert changed.status_code == 200, changed.text
    with sessions() as db:
        admin_id = db.query(User).filter_by(username="demo.admin").one().user_id

    today = date.today()
    found = client.get(
        "/audit/",
        headers=admin,
        params={
            "action": "student.updated",
            "resource": f"student:{student_id}",
            "user_id": admin_id,
            "start": (today - timedelta(days=1)).isoformat(),
            "end": (today + timedelta(days=1)).isoformat(),
        },
    )
    assert found.status_code == 200, found.text
    [entry] = found.json()
    assert entry["actor"] == "demo.admin"
    assert "academic_hold: no → sí" in entry["detail"]
    assert found.headers["X-Total-Count"] == "1"

    sessions_created = client.get("/audit/", headers=admin, params={"action": "session.created"})
    assert sessions_created.json() and all(item["detail"] == "" for item in sessions_created.json())

    future = client.get("/audit/", headers=admin, params={"start": "2999-01-01"})
    assert future.json() == []
    reversed_range = client.get(
        "/audit/", headers=admin, params={"start": "2026-11-21", "end": "2026-11-20"}
    )
    assert reversed_range.status_code == 422
    assert client.get("/audit/", headers=tokens["docente"]).status_code == 403
    assert client.get("/audit/", headers=tokens["estudiante"]).status_code == 403


# Panel principal.


def test_dashboard_summary_depends_on_scope(demo):  # noqa: F811
    client, sessions, tokens = demo
    admin = client.get("/dashboard/summary", headers=tokens["admin"]).json()
    assert admin["role"] == "admin"
    assert {m["key"] for m in admin["metrics"]} == {
        "students",
        "teachers",
        "sections",
        "enrollments",
    }
    assert admin["display_name"] == "equipo de administración"

    teacher = client.get("/dashboard/summary", headers=tokens["docente"]).json()
    assert teacher["role"] == "teacher"
    assert [m["key"] for m in teacher["metrics"]] == ["sections", "students", "grades"]
    assert teacher["metrics"][0]["value"] >= 1

    student = client.get("/dashboard/summary", headers=tokens["estudiante"]).json()
    assert student["role"] == "student"
    assert [m["key"] for m in student["metrics"]] == [
        "courses",
        "average",
        "provisional_average",
        "attendance",
    ]

    with sessions() as db:
        for period in db.query(AcademicPeriod).all():
            period.active = False
        db.commit()
    without_period = client.get("/dashboard/summary", headers=tokens["admin"]).json()
    assert without_period["active_period"] is None
    assert "No hay un período académico activo" in without_period["alerts"]
    assert client.get("/dashboard/summary", headers=tokens["estudiante"]).status_code == 200


# Editor de permisos por rol.


def test_role_permission_editor_validates_and_records_changes(demo):  # noqa: F811
    client, sessions, tokens = demo
    admin = tokens["admin"]
    created = client.post(
        "/roles/",
        headers=admin,
        json={"name": "consulta", "description": "Solo lectura", "label": "Consulta"},
    )
    assert created.status_code == 200, created.text
    target = created.json()["role_id"]
    path = f"/access/roles/{target}/permissions"

    unknown = client.put(path, headers=admin, json={"permissions": ["no.existe"]})
    assert unknown.status_code == 422
    short = client.put(path, headers=admin, json={"permissions": ["students.view"], "reason": "x"})
    assert short.status_code == 422
    stale = client.put(
        path,
        headers=admin,
        json={"permissions": ["students.view"], "expected_permissions": ["grades.view"]},
    )
    assert stale.status_code == 409

    saved = client.put(
        path,
        headers=admin,
        json={
            "permissions": ["students.view", "programs.view"],
            "reason": "Acceso de consulta para secretaría",
            "expected_permissions": [],
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["permissions"] == ["programs.view", "students.view"]
    assert client.get(path, headers=admin).status_code == 200
    history = client.get(f"/access/roles/{target}/history", headers=admin).json()
    assert history[0]["action"] == "role.permissions.updated"
    assert "Acceso de consulta para secretaría" in history[0]["detail"]

    own = f"/access/roles/{role_id(sessions, 'admin')}/permissions"
    removed = client.put(own, headers=admin, json={"permissions": ["students.view"]})
    assert removed.status_code == 409
    assert client.put(path, headers=tokens["docente"], json={"permissions": []}).status_code == 403

    custom = client.post(
        "/access/permissions",
        headers=admin,
        json={"slug": "biblioteca.view", "description": "Consultar biblioteca"},
    )
    assert custom.status_code == 200, custom.text
    catalog = client.get("/access/permissions", headers=admin)
    assert catalog.status_code == 200
    assert client.get("/access/scopes", headers=admin).json()[0]["value"] == "institution"
