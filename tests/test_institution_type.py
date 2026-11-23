"""University, school or both (Fase 3, block A2)."""

from test_write_audit import demo, entries  # noqa: F401  (shared fixtures)

from app.models import Career, Student, User


def settings_payload(client, headers, **changes):
    current = client.get("/configuration/institution", headers=headers).json()
    keys = (
        "institution_name",
        "enrollment_prefix",
        "enrollment_digits",
        "passing_grade",
        "max_credits_per_period",
    )
    return {**{k: current[k] for k in keys}, "reason": "Cambio de tipo", **changes}


def test_existing_installations_are_universities_and_programs_must_fit(demo):  # noqa: F811
    client, sessions, tokens = demo
    admin = tokens["admin"]
    assert client.get("/configuration/institution", headers=admin).json()["institution_type"] == (
        "university"
    )
    school_program = client.post(
        "/careers/",
        headers=admin,
        json={
            "name": "Secundaria",
            "description": "Nivel secundario",
            "academic_level": "secondary",
        },
    )
    assert school_program.status_code == 422
    blocked = client.put(
        "/configuration/institution",
        headers=admin,
        json=settings_payload(client, admin, institution_type="school"),
    )
    assert blocked.status_code == 409  # demo careers are university programs
    assert "Universidad y escuela" in blocked.json()["detail"]


def test_mixed_institution_hides_finances_from_school_students_only(demo):  # noqa: F811
    client, sessions, tokens = demo
    admin = tokens["admin"]
    both = client.put(
        "/configuration/institution",
        headers=admin,
        json=settings_payload(client, admin, institution_type="both"),
    )
    assert both.status_code == 200, both.text
    assert both.json()["students_view_finance"] is True
    with sessions() as db:
        own = db.query(User).filter_by(username="demo.estudiante").one().student_id
    path = f"/finance/students/{own}"
    assert client.get(path, headers=tokens["estudiante"]).status_code == 200
    level = client.post(
        "/careers/",
        headers=admin,
        json={"name": "Primaria", "description": "Nivel primario", "academic_level": "primary"},
    )
    assert level.status_code == 200, level.text
    with sessions() as db:
        db.get(Student, own).career_id = level.json()["career_id"]
        db.commit()
    assert client.get(path, headers=tokens["estudiante"]).status_code == 403
    assert client.get(path, headers=admin).status_code == 200
    assert any("institution_type" in e[2] for e in entries(sessions, "configuration.updated"))


def test_switching_to_school_hides_student_finances_by_default(demo):  # noqa: F811
    client, sessions, tokens = demo
    admin = tokens["admin"]
    with sessions() as db:
        for career in db.query(Career):
            career.academic_level = "secondary"
        db.commit()
    school = client.put(
        "/configuration/institution",
        headers=admin,
        json=settings_payload(client, admin, institution_type="school"),
    )
    assert school.status_code == 200, school.text
    assert school.json()["institution_type"] == "school"
    assert school.json()["students_view_finance"] is False
    university = client.post(
        "/careers/",
        headers=admin,
        json={"name": "Ingeniería", "description": "Grado", "academic_level": "undergraduate"},
    )
    assert university.status_code == 422
