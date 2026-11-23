"""Grading scales per program: validation, labels, passing grade and index (Fase 3 D)."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from test_write_audit import demo, entries  # noqa: F401  (demo is a shared fixture)

from app.models import Enrollment, Grade, InstitutionSettings, Student, User
from app.services import grading_scales as service


def bands(*rows):
    return [
        SimpleNamespace(
            label=label, min_value=low, max_value=high, stored_value=stored, points=None
        )
        for label, low, high, stored in rows
    ]


def letter_view():
    preset = service.PRESETS["letter"]
    return service.ScaleView(
        1,
        preset["name"],
        "letter",
        Decimal("70"),
        bands=[
            service.Band(
                b["label"],
                Decimal(b["min_value"]),
                Decimal(b["max_value"]),
                Decimal(b["stored_value"]),
                Decimal(b["points"]),
            )
            for b in preset["bands"]
        ],
    )


def test_bands_must_cover_zero_to_hundred_without_gaps():
    with pytest.raises(HTTPException, match="cubrir de 0 a 100"):
        service.validate_bands("letter", 70, bands(("F", 0, 70, 60), ("A", 70, 90, 80)))
    with pytest.raises(HTTPException, match="hueco"):
        service.validate_bands("letter", 70, bands(("F", 0, 60, 50), ("A", 70, 100, 90)))
    with pytest.raises(HTTPException, match="valor guardado"):
        service.validate_bands("letter", 70, bands(("F", 0, 70, 75), ("A", 70, 100, 90)))
    with pytest.raises(HTTPException, match="nota mínima"):
        service.validate_bands("letter", 65, bands(("F", 0, 70, 60), ("A", 70, 100, 90)))
    with pytest.raises(HTTPException, match="necesitan rangos"):
        service.validate_bands("conceptual", 70, [])
    service.validate_bands("letter", 70, bands(("F", 0, 70, 60), ("A", 70, 100, 100)))


def test_labels_points_and_index():
    scale = letter_view()
    assert service.label(scale, 69.99) == "F"
    assert service.label(scale, 70) == "D"
    assert service.label(scale, 100) == "A"
    assert service.label(scale, None) is None
    numeric = service.ScaleView(None, "Numérica", "numeric", Decimal("70"), decimals=1)
    assert service.label(numeric, 84.46) == "84.5"
    # (A, 4 credits) and (C, 2 credits): (4*4 + 2*2) / 6 = 3.33
    assert service.academic_index([(95, 4), (76, 2), (None, 3), (60, 0)], scale) == 3.33
    assert service.academic_index([(95, 4)], numeric) is None


def test_conceptual_capture_only_accepts_band_values():
    preset = service.PRESETS["conceptual"]
    scale = service.ScaleView(
        2,
        preset["name"],
        "conceptual",
        Decimal("65"),
        bands=[
            service.Band(
                b["label"],
                Decimal(b["min_value"]),
                Decimal(b["max_value"]),
                Decimal(b["stored_value"]),
            )
            for b in preset["bands"]
        ],
    )
    service.ensure_capturable(scale, 75)
    with pytest.raises(HTTPException, match="Iniciado, En proceso, Logrado"):
        service.ensure_capturable(scale, 80)


def letter_payload(**changes):
    return {**service.PRESETS["letter"], "name": "Letras universidad", **changes}


def test_scale_api_assignment_snapshot_and_transcript(demo):  # noqa: F811
    client, sessions, tokens = demo
    admin = tokens["admin"]
    with sessions() as db:
        if db.get(InstitutionSettings, 1) is None:
            db.add(InstitutionSettings(settings_id=1))
            db.commit()
    presets = client.get("/grading-scales/presets", headers=admin)
    assert {p["key"] for p in presets.json()} == {"numeric", "letter", "conceptual"}
    assert (
        client.post(
            "/grading-scales/", headers=tokens["docente"], json=letter_payload()
        ).status_code
        == 403
    )
    created = client.post("/grading-scales/", headers=admin, json=letter_payload())
    assert created.status_code == 200, created.text
    scale = created.json()
    assert [b["label"] for b in scale["bands"]] == ["F", "D", "C", "B", "A"]
    # Nothing was configured before: the first scale becomes the default.
    assert scale["is_default"] is True
    duplicate = client.post("/grading-scales/", headers=admin, json=letter_payload())
    assert duplicate.status_code == 409
    gap = client.post(
        "/grading-scales/",
        headers=admin,
        json=letter_payload(name="Con hueco", bands=service.PRESETS["letter"]["bands"][1:]),
    )
    assert gap.status_code == 422
    stricter = client.put(
        f"/grading-scales/{scale['grading_scale_id']}",
        headers=admin,
        json=letter_payload(
            passing_value=75,
            bands=[
                {"label": "F", "min_value": 0, "max_value": 75, "stored_value": 60, "points": 0},
                {"label": "C", "min_value": 75, "max_value": 80, "stored_value": 77, "points": 2},
                {"label": "B", "min_value": 80, "max_value": 90, "stored_value": 85, "points": 3},
                {"label": "A", "min_value": 90, "max_value": 100, "stored_value": 95, "points": 4},
            ],
        ),
    )
    assert stricter.status_code == 200, stricter.text
    with sessions() as db:
        # The default scale and the institution's passing grade are the same value.
        assert db.get(InstitutionSettings, 1).passing_grade == 75
        student = db.query(User).filter_by(username="demo.estudiante").one().student_id
        career_id = db.get(Student, student).career_id
    restored = client.put(
        f"/grading-scales/{scale['grading_scale_id']}", headers=admin, json=letter_payload()
    )
    assert restored.status_code == 200
    assigned = client.patch(
        f"/careers/{career_id}",
        headers=admin,
        json={"grading_scale_id": scale["grading_scale_id"]},
    )
    assert assigned.status_code == 200, assigned.text
    assert (
        client.patch(
            f"/careers/{career_id}", headers=admin, json={"grading_scale_id": 999}
        ).status_code
        == 422
    )
    deleted = client.delete(f"/grading-scales/{scale['grading_scale_id']}", headers=admin)
    assert deleted.status_code == 409
    with sessions() as db:
        enrollment = db.query(Enrollment).filter_by(student_id=student).first()
        enrollment.passing_grade = 70
        db.add(
            Grade(
                enrollment_id=enrollment.enrollment_id,
                grade_value=86,
                grade_type="final",
                date_recorded=date(2026, 5, 1),
                status="published",
            )
        )
        for grade in enrollment.grades:
            if grade.assessment_id is not None:
                db.delete(grade)
        db.commit()
    transcript = client.get(f"/records/students/{student}/transcript", headers=admin)
    assert transcript.status_code == 200, transcript.text
    body = transcript.json()
    assert body["grading_scale_name"] == "Letras universidad"
    assert any(course["average_label"] in {"A", "B", "C", "D", "F"} for course in body["courses"])
    profile = client.get(f"/academic/students/{student}/profile", headers=admin).json()
    assert profile["grading_scale"]["kind"] == "letter"
    assert entries(sessions, "grading_scale.created", f"grading-scale:{scale['grading_scale_id']}")


def test_new_selection_keeps_the_program_passing_grade(demo):  # noqa: F811
    client, sessions, tokens = demo
    admin = tokens["admin"]
    scale = client.post(
        "/grading-scales/",
        headers=admin,
        json={**service.PRESETS["conceptual"], "name": "Conceptual inicial"},
    ).json()
    with sessions() as db:
        student = db.query(User).filter_by(username="demo.estudiante").one().student_id
        career_id = db.get(Student, student).career_id
    client.patch(
        f"/careers/{career_id}", headers=admin, json={"grading_scale_id": scale["grading_scale_id"]}
    )
    with sessions() as db:
        student_row = db.get(Student, student)
        assert service.passing_for(db, student_row) == 65.0
