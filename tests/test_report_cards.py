"""School report cards, homeroom remarks and period reports (Fase 3 F)."""

from datetime import datetime

from test_class_groups import create_group, publish_final, school  # noqa: F401
from test_write_audit import demo, entries  # noqa: F401

from app.models import (
    AcademicPeriod,
    Attendance,
    Enrollment,
    Guardian,
    InstitutionSettings,
    Role,
    Section,
    StudentGuardian,
    User,
)
from app.security import hash_password


def login(client, username, password):
    token = client.post("/auth/login", json={"username": username, "password": password})
    assert token.status_code == 200, token.text
    return {"Authorization": "Bearer " + token.json()["access_token"]}


def setup_group(school):  # noqa: F811
    client, sessions, tokens, ids = school
    admin = tokens["admin"]
    gid = create_group(client, admin, ids)["class_group_id"]
    for student_id in ids["students"][:2]:
        client.post(f"/class-groups/{gid}/members", headers=admin, json={"student_id": student_id})
    client.post(f"/class-groups/{gid}/generate-subjects", headers=admin)
    first, second = ids["students"][:2]
    math = ids["subjects"][0]
    with sessions() as db:
        settings = db.get(InstitutionSettings, 1) or InstitutionSettings(settings_id=1)
        settings.school_code, settings.regional, settings.district = "12345", "10", "10-03"
        db.add(settings)
        period_one = (
            db.query(AcademicPeriod)
            .filter_by(school_year_id=ids["years"][0])
            .order_by(AcademicPeriod.start_date)
            .first()
        )
        period_one.status = "closed"
        for enrollment in (
            db.query(Enrollment)
            .join(Section)
            .filter(Section.class_group_id == gid, Section.period_id == period_one.period_id)
        ):
            value = (
                62
                if enrollment.student_id == second and enrollment.section.subject_id == math
                else 88
            )
            publish_final(db, enrollment, value)
            db.add_all(
                Attendance(
                    enrollment_id=enrollment.enrollment_id,
                    date=datetime(2026, 9, day, 8),
                    present=status != "absent",
                    status=status,
                )
                for day, status in ((1, "present"), (2, "late"), (3, "absent"))
            )
        db.commit()
        period_id = period_one.period_id
    return client, sessions, tokens, ids, gid, period_id


def test_report_card_grades_attendance_and_pdf(school):  # noqa: F811
    client, sessions, tokens, ids, gid, period_id = setup_group(school)
    admin = tokens["admin"]
    first, second = ids["students"][:2]
    card = client.get(f"/students/{second}/report-card", headers=admin)
    assert card.status_code == 200, card.text
    body = card.json()
    assert body["institution"]["school_code"] == "12345"
    assert body["group_label"] == "1.º A · Secundaria" and body["school_year"] == "2026-2027"
    assert [p["short"] for p in body["periods"]] == ["P1", "P2", "P3", "P4"]
    math = body["subjects"][0]
    # Only P1 is final; later periods are still running.
    assert math["periods"] == ["62", None, None, None] and math["status"] == "incomplete"
    assert math["status_label"] == "En curso" and math["final"] is None
    assert body["attendance"][0] == {
        "period": body["periods"][0]["name"],
        "present": 2 * 1,
        "late": 2 * 1,
        "absent": 2 * 1,
        "excused": 0,
        "total": 6,
        "percentage": 66.7,
    }
    assert body["result_label"] == "Pendiente"
    pdf = client.get(f"/students/{second}/report-card.pdf", headers=admin)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    # The old endpoint switches to the school format for school students.
    legacy = client.get(f"/documents/students/{second}/report-card.pdf", headers=admin)
    assert legacy.status_code == 200 and "2026-2027" in legacy.headers["content-disposition"]
    group_pdf = client.get(f"/class-groups/{gid}/report-cards.pdf", headers=admin)
    assert group_pdf.status_code == 200 and group_pdf.content.startswith(b"%PDF")
    assert (
        client.get(f"/students/{second}/report-card", headers=tokens["estudiante"]).status_code
        == 403
    )
    assert (
        client.get(
            f"/students/{second}/report-card?school_year_id={ids['years'][1]}", headers=admin
        ).status_code
        == 404
    )


def test_family_and_student_see_their_card_unless_restricted(school):  # noqa: F811
    client, sessions, tokens, ids, gid, period_id = setup_group(school)
    first = ids["students"][0]
    with sessions() as db:
        student_role = db.query(Role).filter_by(name="student").one()
        guardian_role = db.query(Role).filter_by(name="guardian").first()
        if guardian_role is None:
            guardian_role = Role(name="guardian", description="Tutor")
            db.add(guardian_role)
            db.flush()
        guardian = Guardian(
            first_name="Rosa", last_name="Peña", email="rosa@nexo-academico.com", telephone="809"
        )
        db.add(guardian)
        db.flush()
        link = StudentGuardian(
            student_id=first, guardian_id=guardian.guardian_id, relationship="Madre"
        )
        db.add(link)
        db.add_all(
            [
                User(
                    username="alumno.001",
                    email="alumno001@nexo-academico.com",
                    password=hash_password("NexoAlumno2026!"),
                    role_id=student_role.role_id,
                    student_id=first,
                ),
                User(
                    username="rosa.pena",
                    email="rosa.user@nexo-academico.com",
                    password=hash_password("NexoTutor2026!"),
                    role_id=guardian_role.role_id,
                    guardian_id=guardian.guardian_id,
                ),
            ]
        )
        db.commit()
        link_id = link.student_guardian_id
    student = login(client, "alumno.001", "NexoAlumno2026!")
    guardian = login(client, "rosa.pena", "NexoTutor2026!")
    assert client.get(f"/students/{first}/report-card", headers=student).status_code == 200
    assert client.get(f"/students/{first}/report-card", headers=guardian).status_code == 200
    assert (
        client.get(f"/students/{ids['students'][1]}/report-card", headers=guardian).status_code
        == 403
    )
    with sessions() as db:
        db.get(StudentGuardian, link_id).can_view_academic = False
        db.commit()
    assert client.get(f"/students/{first}/report-card", headers=guardian).status_code == 403


def test_homeroom_remarks(school):  # noqa: F811
    client, sessions, tokens, ids, gid, period_id = setup_group(school)
    first = ids["students"][0]
    with sessions() as db:
        db.query(User).filter_by(username="demo.docente").one().teacher_id = ids["teacher"]
        db.commit()
    group = client.get(f"/class-groups/{gid}", headers=tokens["admin"]).json()
    member = next(m for m in group["members"] if m["student_id"] == first)["member_id"]
    path = f"/class-groups/{gid}/members/{member}/comments/{period_id}"
    saved = client.put(path, headers=tokens["docente"], json={"comment": "Muy participativo."})
    assert saved.status_code == 200, saved.text
    assert saved.json()["comments"][0]["comment"] == "Muy participativo."
    assert client.put(path, headers=tokens["estudiante"], json={"comment": "x"}).status_code == 403
    teacher_view = client.get(f"/students/{first}/report-card", headers=tokens["docente"])
    assert teacher_view.status_code == 200
    cleared = client.put(path, headers=tokens["admin"], json={"comment": "  "})
    assert cleared.json()["comments"] == []
    assert entries(sessions, "report_card.comment", f"class-group:{gid}")


def test_period_report_and_promotion_summary(school):  # noqa: F811
    client, sessions, tokens, ids, gid, period_id = setup_group(school)
    admin = tokens["admin"]
    report = client.get(f"/class-groups/{gid}/period-report?period_id={period_id}", headers=admin)
    assert report.status_code == 200, report.text
    body = report.json()
    assert body["closed"] is True
    math = body["subjects"][0]
    assert math["average"] == 75.0 and math["passed_percentage"] == 50.0
    below = {s["student_name"]: s["below_passing"] for s in body["students"]}
    assert below == {"Alumno 001": [], "Alumno 002": ["SEC-MAT1"]}
    csv = client.get(f"/class-groups/{gid}/period-report.csv?period_id={period_id}", headers=admin)
    assert csv.status_code == 200 and "SEC-MAT1" in csv.text and "% aprobados" in csv.text
    pdf = client.get(f"/class-groups/{gid}/period-report.pdf?period_id={period_id}", headers=admin)
    assert pdf.content.startswith(b"%PDF")
    summary = client.get(f"/school-years/{ids['years'][0]}/promotion-summary", headers=admin).json()
    assert summary == [
        {
            "class_group_id": gid,
            "label": "1.º A · Secundaria",
            "career_name": "Secundaria",
            "grade_number": 1,
            "students": 2,
            "promoted": 0,
            "completivo": 0,
            "extraordinario": 0,
            "repeated": 0,
            "pending": 2,
        }
    ]
    assert (
        client.get(
            f"/school-years/{ids['years'][0]}/promotion-summary", headers=tokens["estudiante"]
        ).json()
        == []
    )
