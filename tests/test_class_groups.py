"""Fixed school groups: members, subjects per period, promotion and re-enrollment (Fase 3 C)."""

from datetime import date

import pytest
from test_write_audit import demo, entries  # noqa: F401  (demo is a shared fixture)

from app.models import (
    Career,
    CurriculumCourse,
    Enrollment,
    Grade,
    Section,
    Student,
    Subject,
    Teacher,
    User,
)
from app.models.configuration_model import SchoolYear
from app.services.school_years import generate_periods


def make_student(db, career, number, **extra):
    student = Student(
        first_name="Alumno",
        last_name=f"{number:03d}",
        email=f"alumno{number}@escuela.test",
        enrollment_number=f"ESC-{number:03d}",
        telephone="809-000-0000",
        address="Santo Domingo",
        career_id=career.career_id,
        **extra,
    )
    db.add(student)
    return student


@pytest.fixture
def school(demo):  # noqa: F811
    """Secundaria (6 annual grades), two subjects per grade and two school years."""
    client, sessions, tokens = demo
    with sessions() as db:
        career = Career(
            name="Secundaria",
            description="Nivel secundario",
            code="SEC",
            academic_level="secondary",
            term_type="annual",
            duration_terms=6,
            required_credits=0,
        )
        db.add(career)
        db.flush()
        by_grade = {
            grade: [
                Subject(code=f"SEC-{c}{grade}", description=f"{n} {grade}")
                for c, n in (("MAT", "Matemática"), ("LEN", "Lengua"))
            ]
            for grade in (1, 2)
        }
        db.add_all(by_grade[1] + by_grade[2])
        db.flush()
        subjects = by_grade[1]
        for grade, grade_subjects in by_grade.items():
            for subject in grade_subjects:
                db.add(
                    CurriculumCourse(
                        career_id=career.career_id,
                        subject_id=subject.subject_id,
                        term_number=grade,
                        credits=0,
                    )
                )
        teacher = db.query(Teacher).first()
        years = []
        for name, start, end in (
            ("2026-2027", date(2026, 8, 17), date(2027, 6, 18)),
            ("2027-2028", date(2027, 8, 16), date(2028, 6, 16)),
        ):
            year = SchoolYear(name=name, start_date=start, end_date=end, period_scheme="quarters")
            db.add(year)
            db.flush()
            db.refresh(year)
            generate_periods(db, year)
            years.append(year.school_year_id)
        students = [make_student(db, career, n) for n in range(1, 4)]
        held = make_student(db, career, 9, financial_hold=True)
        db.commit()
        ids = {
            "career": career.career_id,
            "teacher": teacher.teacher_id,
            "years": years,
            "students": [s.student_id for s in students],
            "held": held.student_id,
            "subjects": [s.subject_id for s in subjects],
        }
    return client, sessions, tokens, ids


def create_group(client, admin, ids, grade=1, name="a", year=0, **extra):
    response = client.post(
        "/class-groups/",
        headers=admin,
        json={
            "career_id": ids["career"],
            "grade_number": grade,
            "name": name,
            "school_year_id": ids["years"][year],
            "homeroom_teacher_id": ids["teacher"],
            **extra,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_groups_only_for_school_programs_and_unique_per_year(school):
    client, sessions, tokens, ids = school
    admin = tokens["admin"]
    group = create_group(client, admin, ids)
    assert group["name"] == "A" and group["label"] == "1.º A · Secundaria"
    duplicate = client.post(
        "/class-groups/",
        headers=admin,
        json={
            "career_id": ids["career"],
            "grade_number": 1,
            "name": "A",
            "school_year_id": ids["years"][0],
        },
    )
    assert duplicate.status_code == 409
    with sessions() as db:
        university = db.query(Career).filter(Career.academic_level != "secondary").first()
        university_id = university.career_id
    wrong = client.post(
        "/class-groups/",
        headers=admin,
        json={
            "career_id": university_id,
            "grade_number": 1,
            "name": "A",
            "school_year_id": ids["years"][0],
        },
    )
    assert wrong.status_code == 409
    too_high = client.post(
        "/class-groups/",
        headers=admin,
        json={
            "career_id": ids["career"],
            "grade_number": 7,
            "name": "A",
            "school_year_id": ids["years"][0],
        },
    )
    assert too_high.status_code == 422
    # A student without a teacher link or academic reach sees no group at all.
    assert client.get("/class-groups/", headers=tokens["estudiante"]).json() == []
    path = f"/class-groups/{group['class_group_id']}"
    assert client.get(path, headers=tokens["estudiante"]).status_code == 403
    assert client.post("/class-groups/", headers=tokens["docente"], json={}).status_code == 403


def test_subjects_members_transfer_and_withdrawal(school):
    client, sessions, tokens, ids = school
    admin = tokens["admin"]
    group = create_group(client, admin, ids)
    other = create_group(client, admin, ids, name="B")
    gid = group["class_group_id"]
    for student_id in ids["students"][:2]:
        added = client.post(
            f"/class-groups/{gid}/members", headers=admin, json={"student_id": student_id}
        )
        assert added.status_code == 200, added.text
    generated = client.post(f"/class-groups/{gid}/generate-subjects", headers=admin)
    assert generated.status_code == 200, generated.text
    assert generated.json() == {"sections_created": 8, "enrollments_created": 16}
    again = client.post(f"/class-groups/{gid}/generate-subjects", headers=admin).json()
    assert again == {"sections_created": 0, "enrollments_created": 0}
    # A late member joins every open-period subject; one group per student and year.
    late = client.post(
        f"/class-groups/{gid}/members", headers=admin, json={"student_id": ids["students"][2]}
    )
    assert late.status_code == 200
    twice = client.post(
        f"/class-groups/{other['class_group_id']}/members",
        headers=admin,
        json={"student_id": ids["students"][2]},
    )
    assert twice.status_code == 409 and "ya está en 1.º A" in twice.json()["detail"]
    with sessions() as db:
        assert db.query(Enrollment).filter_by(student_id=ids["students"][2]).count() == 8
        codes = {s.code for s in db.query(Section).filter_by(class_group_id=gid)}
        assert "SEC-MAT1-1A-2026-2027-P1" in codes
    detail = late.json()
    assert [s["sections"] for s in detail["subjects"]] == [4, 4]
    assert len(detail["open_periods"]) == 4
    member = next(m for m in detail["members"] if m["student_id"] == ids["students"][2])
    moved = client.post(
        f"/class-groups/{gid}/members/{member['member_id']}/transfer",
        headers=admin,
        json={"target_group_id": other["class_group_id"], "reason": "Cambio de tanda"},
    )
    assert moved.status_code == 200, moved.text
    assert all(m["student_id"] != ids["students"][2] for m in moved.json()["members"])
    with sessions() as db:
        states = {e.state for e in db.query(Enrollment).filter_by(student_id=ids["students"][2])}
        assert states == {"withdrawn"}  # group B has no subjects yet
    first = next(m for m in moved.json()["members"] if m["student_id"] == ids["students"][0])
    withdrawn = client.post(
        f"/class-groups/{gid}/members/{first['member_id']}/withdraw",
        headers=admin,
        json={"reason": "Traslado a otro centro"},
    )
    assert withdrawn.status_code == 200
    with sessions() as db:
        assert {e.state for e in db.query(Enrollment).filter_by(student_id=ids["students"][0])} == {
            "withdrawn"
        }
    assert entries(sessions, "class_group.subjects_generated", f"class-group:{gid}")
    assert entries(sessions, "class_group.member_withdrawn", f"class-group:{gid}")
    # The homeroom teacher sees the group because they teach its subjects.
    with sessions() as db:
        teacher_user = db.query(User).filter_by(username="demo.docente").one()
        teacher_user.teacher_id = ids["teacher"]
        db.commit()
    seen = client.get("/class-groups/", headers=tokens["docente"]).json()
    assert {g["class_group_id"] for g in seen} == {gid, other["class_group_id"]}


def test_subject_teacher_follows_open_sections(school):
    client, sessions, tokens, ids = school
    admin = tokens["admin"]
    gid = create_group(client, admin, ids)["class_group_id"]
    client.post(f"/class-groups/{gid}/generate-subjects", headers=admin)
    with sessions() as db:
        teacher = Teacher(
            first_name="Ana",
            last_name="Pérez",
            specialty="Matemática",
            email="ana.perez@escuela.test",
            telephone="809-000-0001",
            address="Santo Domingo",
        )
        db.add(teacher)
        db.commit()
        other_teacher = teacher.teacher_id
    changed = client.put(
        f"/class-groups/{gid}/subjects/{ids['subjects'][0]}",
        headers=admin,
        json={"teacher_id": other_teacher},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["subjects"][0]["teacher_id"] == other_teacher
    with sessions() as db:
        teachers = {
            s.teacher_id
            for s in db.query(Section).filter_by(class_group_id=gid, subject_id=ids["subjects"][0])
        }
        assert teachers == {other_teacher}


def test_financial_hold_needs_an_exception_from_finance(school):
    client, sessions, tokens, ids = school
    admin = tokens["admin"]
    gid = create_group(client, admin, ids)["class_group_id"]
    blocked = client.post(
        f"/class-groups/{gid}/members", headers=admin, json={"student_id": ids["held"]}
    )
    assert blocked.status_code == 409 and "financiero" in blocked.json()["detail"]
    allowed = client.post(
        f"/class-groups/{gid}/members",
        headers=admin,
        json={"student_id": ids["held"], "override_reason": "Acuerdo de pago firmado"},
    )
    assert allowed.status_code == 200, allowed.text
    detail = entries(sessions, "class_group.member_added", f"class-group:{gid}")[-1][2]
    assert "excepción al bloqueo financiero: Acuerdo de pago firmado" in detail


def publish_final(db, enrollment, value):
    db.add(
        Grade(
            enrollment_id=enrollment.enrollment_id,
            grade_value=value,
            grade_type="final",
            date_recorded=date(2027, 6, 1),
            status="published",
        )
    )


def test_promotion_proposal_confirmation_and_reinscription(school):
    client, sessions, tokens, ids = school
    admin = tokens["admin"]
    gid = create_group(client, admin, ids)["class_group_id"]
    for student_id in ids["students"][:2]:
        client.post(f"/class-groups/{gid}/members", headers=admin, json={"student_id": student_id})
    client.post(f"/class-groups/{gid}/generate-subjects", headers=admin)
    pending = client.get(f"/class-groups/{gid}/promotion", headers=admin).json()
    assert {row["proposal"] for row in pending["members"]} == {None}  # no grades yet
    good, weak = ids["students"][:2]
    with sessions() as db:
        for enrollment in db.query(Enrollment).filter(Enrollment.student_id.in_([good, weak])):
            failing = (
                enrollment.student_id == weak
                and enrollment.section.subject_id == ids["subjects"][0]
            )
            publish_final(db, enrollment, 60 if failing else 85)
        db.commit()
    proposal = client.get(f"/class-groups/{gid}/promotion", headers=admin).json()
    rows = {row["student_id"]: row for row in proposal["members"]}
    assert proposal["passing_grade"] == 70
    assert rows[good]["proposal"] == "promoted"
    assert rows[weak]["proposal"] == "completivo" and rows[weak]["failed"] == ["SEC-MAT1"]
    assert rows[weak]["subjects"][0]["average"] == 60.0
    target = create_group(client, admin, ids, grade=2, year=1)
    same_grade = create_group(client, admin, ids, grade=1, year=1)
    early = client.post(
        f"/class-groups/{gid}/reinscribe",
        headers=admin,
        json={"target_group_id": target["class_group_id"], "member_ids": [rows[good]["member_id"]]},
    ).json()
    assert early["reinscribed"] == [] and "sin confirmar" in early["blocked"][0]["reason"]
    confirmed = client.post(
        f"/class-groups/{gid}/promotion",
        headers=admin,
        json={
            "decisions": [
                {"member_id": rows[good]["member_id"], "result": "promoted"},
                {
                    "member_id": rows[weak]["member_id"],
                    "result": "repeated",
                    "note": "No aprobó el completivo",
                },
            ]
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    members = [rows[good]["member_id"], rows[weak]["member_id"]]
    to_second = client.post(
        f"/class-groups/{gid}/reinscribe",
        headers=admin,
        json={"target_group_id": target["class_group_id"], "member_ids": members},
    ).json()
    assert to_second["reinscribed"] == ["Alumno 001"]
    assert "Le corresponde el grado 1" in to_second["blocked"][0]["reason"]
    to_first = client.post(
        f"/class-groups/{gid}/reinscribe",
        headers=admin,
        json={
            "target_group_id": same_grade["class_group_id"],
            "member_ids": [rows[weak]["member_id"]],
        },
    ).json()
    assert to_first["reinscribed"] == ["Alumno 002"]
    backwards = client.post(
        f"/class-groups/{target['class_group_id']}/reinscribe",
        headers=admin,
        json={"target_group_id": gid, "member_ids": [1]},
    )
    assert backwards.status_code == 409
    assert entries(sessions, "class_group.result_confirmed", f"class-group:{gid}")


def test_completivo_then_extraordinario_with_scale_weights(school):
    client, sessions, tokens, ids = school
    admin = tokens["admin"]
    gid = create_group(client, admin, ids)["class_group_id"]
    student = ids["students"][0]
    client.post(f"/class-groups/{gid}/members", headers=admin, json={"student_id": student})
    client.post(f"/class-groups/{gid}/generate-subjects", headers=admin)
    math = ids["subjects"][0]
    with sessions() as db:
        for enrollment in db.query(Enrollment).filter_by(student_id=student):
            publish_final(db, enrollment, 60 if enrollment.section.subject_id == math else 80)
        db.commit()
    proposal = client.get(f"/class-groups/{gid}/promotion", headers=admin).json()
    row = proposal["members"][0]
    assert row["proposal"] == "completivo"
    assert proposal["completivo_average_weight"] == 50
    assert row["subjects"][0]["status"] == "completivo"
    path = f"/class-groups/{gid}/members/{row['member_id']}/recovery"
    early = client.post(
        path, headers=admin, json={"subject_id": math, "kind": "extraordinario", "exam_grade": 90}
    )
    assert early.status_code == 409 and "completivo" in early.json()["detail"]
    passed_subject = client.post(
        path,
        headers=admin,
        json={"subject_id": ids["subjects"][1], "kind": "completivo", "exam_grade": 90},
    )
    assert passed_subject.status_code == 409 and "aprobada" in passed_subject.json()["detail"]
    # 50 % of 60 + 50 % of 70 = 65 < 70: the extraordinario comes next.
    completivo = client.post(
        path, headers=admin, json={"subject_id": math, "kind": "completivo", "exam_grade": 70}
    )
    assert completivo.status_code == 200, completivo.text
    subject = completivo.json()["members"][0]["subjects"][0]
    assert subject["completivo"] == 65 and subject["status"] == "extraordinario"
    assert completivo.json()["members"][0]["proposal"] == "extraordinario"
    # 30 % of 60 + 70 % of 75 = 70.5: passes, and the student is promoted.
    extraordinario = client.post(
        path,
        headers=admin,
        json={"subject_id": math, "kind": "extraordinario", "exam_grade": 75},
    )
    row = extraordinario.json()["members"][0]
    assert row["subjects"][0]["extraordinario"] == 70.5
    assert row["proposal"] == "promoted"
    locked = client.post(
        path, headers=admin, json={"subject_id": math, "kind": "completivo", "exam_grade": 80}
    )
    assert locked.status_code == 409
    details = [entry[2] for entry in entries(sessions, "class_group.recovery_recorded")]
    assert any("completivo 70" in detail and "→ 65.00 reprobada" in detail for detail in details)
    assert (
        client.post(
            path,
            headers=tokens["estudiante"],
            json={"subject_id": math, "kind": "completivo", "exam_grade": 80},
        ).status_code
        == 403
    )
