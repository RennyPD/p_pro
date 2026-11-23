"""Official MINERD secondary report card: competencies, header data, special evaluation (F2)."""

from datetime import date

from test_class_groups import create_group, school  # noqa: F401
from test_write_audit import demo, entries  # noqa: F401

from app.models import (
    AcademicPeriod,
    Assessment,
    Career,
    Enrollment,
    Grade,
    InstitutionSettings,
    Section,
    Student,
)


def official_group(school, shift="matutina"):  # noqa: F811
    client, sessions, tokens, ids = school
    admin = tokens["admin"]
    with sessions() as db:
        db.get(Career, ids["career"]).report_card_format = "minerd_secondary"
        settings = db.get(InstitutionSettings, 1) or InstitutionSettings(settings_id=1)
        settings.school_code, settings.province, settings.municipality = (
            "05123",
            "Santo Domingo",
            "Santo Domingo Este",
        )
        settings.school_phone = "809-555-0101"
        db.add(settings)
        db.get(Student, ids["students"][0]).sigerd_id = "SIG-0001"
        db.commit()
    gid = create_group(client, admin, ids, shift=shift)["class_group_id"]
    for student_id in ids["students"][:2]:
        client.post(f"/class-groups/{gid}/members", headers=admin, json={"student_id": student_id})
    generated = client.post(f"/class-groups/{gid}/generate-subjects", headers=admin)
    assert generated.status_code == 200, generated.text
    return client, sessions, tokens, ids, gid


def grade_period(sessions, gid, period_index, values):
    """Publish and close every competency of one period; values[student] = 4 grades."""
    with sessions() as db:
        periods = (
            db.query(AcademicPeriod)
            .join(Section, Section.period_id == AcademicPeriod.period_id)
            .filter(Section.class_group_id == gid)
            .order_by(AcademicPeriod.start_date)
            .distinct()
            .all()
        )
        period = periods[period_index]
        for section in db.query(Section).filter_by(class_group_id=gid, period_id=period.period_id):
            assessments = (
                db.query(Assessment)
                .filter_by(section_id=section.section_id)
                .order_by(Assessment.competency_group_id)
                .all()
            )
            for enrollment in db.query(Enrollment).filter_by(section_id=section.section_id):
                for assessment, value in zip(assessments, values[enrollment.student_id]):
                    db.add(
                        Grade(
                            enrollment_id=enrollment.enrollment_id,
                            assessment_id=assessment.assessment_id,
                            grade_value=value,
                            grade_type=assessment.name,
                            date_recorded=date(2026, 10, 1),
                            status="published",
                        )
                    )
            for assessment in assessments:
                assessment.closed = True
        db.commit()


def test_competency_assessments_and_official_card(school):  # noqa: F811
    client, sessions, tokens, ids, gid = official_group(school)
    admin = tokens["admin"]
    first, second = ids["students"][:2]
    with sessions() as db:
        section = db.query(Section).filter_by(class_group_id=gid).first()
        assessments = db.query(Assessment).filter_by(section_id=section.section_id).all()
        assert sorted(a.weight for a in assessments) == [25, 25, 25, 25]
        assert {a.competency_group_id for a in assessments} == {1, 2, 3, 4}
    # Generating again creates nothing new.
    again = client.post(f"/class-groups/{gid}/generate-subjects", headers=admin).json()
    assert again["sections_created"] == 0
    grade_period(sessions, gid, 0, {first: [80, 90, 70, 100], second: [60, 64, 70, 66]})
    card = client.get(f"/students/{first}/report-card", headers=admin).json()
    assert card["format"] == "minerd_secondary"
    assert card["sigerd_id"] == "SIG-0001" and card["shift"] == "matutina"
    assert card["institution"]["province"] == "Santo Domingo"
    assert card["institution"]["phone"] == "809-555-0101"
    assert card["order_number"] == 1 and card["last_name"] == "001"
    assert len(card["competency_groups"]) == 4 and card["competency_groups"][0] == "Comunicativa"
    math = card["subjects"][0]
    # Four competency rows; P1 published, the rest still running.
    assert math["competencies"] == [
        ["80", None, None, None],
        ["90", None, None, None],
        ["70", None, None, None],
        ["100", None, None, None],
    ]
    assert math["periods"][0] == "85"  # PC1 = average of the four groups
    assert card["periods"][0]["months"].startswith("Ago")
    pdf = client.get(f"/students/{first}/report-card.pdf", headers=admin)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    group_pdf = client.get(f"/class-groups/{gid}/report-cards.pdf", headers=admin)
    assert group_pdf.content.startswith(b"%PDF")


def test_special_evaluation_replaces_the_final_grade_when_it_passes(school):  # noqa: F811
    client, sessions, tokens, ids, gid = official_group(school)
    admin = tokens["admin"]
    first, second = ids["students"][:2]
    low = {first: [90, 90, 90, 90], second: [50, 50, 50, 50]}
    for index in range(4):
        grade_period(sessions, gid, index, low)
    proposal = client.get(f"/class-groups/{gid}/promotion", headers=admin).json()
    row = next(r for r in proposal["members"] if r["student_id"] == second)
    math = ids["subjects"][0]
    path = f"/class-groups/{gid}/members/{row['member_id']}/recovery"
    passed_row = next(r for r in proposal["members"] if r["student_id"] == first)
    not_needed = client.post(
        f"/class-groups/{gid}/members/{passed_row['member_id']}/recovery",
        headers=admin,
        json={"subject_id": math, "kind": "especial", "exam_grade": 90},
    )
    assert not_needed.status_code == 409
    special = client.post(
        path, headers=admin, json={"subject_id": math, "kind": "especial", "exam_grade": 75}
    )
    assert special.status_code == 200, special.text
    subject = next(r for r in special.json()["members"] if r["student_id"] == second)["subjects"][0]
    assert subject["especial"] == 75 and subject["status"] == "passed"
    card = client.get(f"/students/{second}/report-card", headers=admin).json()
    math_card = card["subjects"][0]
    assert math_card["final"] == "75" and math_card["situation"] == "A"
    assert math_card["recovery"]["especial"]["exam"] == 75
    assert card["subjects"][1]["situation"] == "R"  # Lengua still failed
    assert any("especial 75" in e[2] for e in entries(sessions, "class_group.recovery_recorded"))
    pdf = client.get(f"/students/{second}/report-card.pdf", headers=admin)
    assert pdf.content.startswith(b"%PDF")


def test_header_data_is_editable(demo):  # noqa: F811
    client, sessions, tokens = demo
    admin = tokens["admin"]
    with sessions() as db:
        student = db.query(Student).first().student_id
    updated = client.patch(f"/students/{student}", headers=admin, json={"sigerd_id": "SIG-777"})
    assert updated.status_code == 200, updated.text
    assert updated.json()["sigerd_id"] == "SIG-777"
    assert entries(sessions, "student.updated", f"student:{student}")[-1][2].find("SIG-777") >= 0
