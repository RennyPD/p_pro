"""Periods are linked by id: renaming keeps every section and selection (audit B5)."""

from test_write_audit import demo  # noqa: F401  (shared fixture)

from app.models import AcademicPeriod, Enrollment, Section


def test_renaming_a_period_in_use_keeps_sections_and_selections(demo):  # noqa: F811
    client, sessions, tokens = demo
    with sessions() as db:
        period = db.query(AcademicPeriod).filter_by(active=True).one()
        period_id, old = period.period_id, period.name
        sections = db.query(Section).filter_by(period_id=period_id).count()
        selections = db.query(Enrollment).filter_by(period_id=period_id).count()
    assert selections  # demo sections have no period; its selections do
    renamed = client.patch(
        f"/periods/{period_id}", headers=tokens["admin"], json={"name": f"{old} (renombrado)"}
    )
    assert renamed.status_code == 200, renamed.text
    with sessions() as db:
        new = f"{old} (renombrado)"
        assert db.query(Section).filter(Section.period_name == new).count() == sections
        assert db.query(Enrollment).filter(Enrollment.period == new).count() == selections
        assert db.query(Section).filter(Section.period_name == old).count() == 0
    listed = client.get("/enrollments/", headers=tokens["admin"], params={"limit": 5}).json()
    assert listed and all(item["period"] == f"{old} (renombrado)" for item in listed)


def test_unknown_period_names_are_rejected_and_empty_means_no_period(demo):  # noqa: F811
    client, sessions, tokens = demo
    with sessions() as db:
        source = db.query(Section).filter_by(code="PROG-101-A").one()
        values = {"teacher_id": source.teacher_id, "subject_id": source.subject_id}
    base = {
        **values,
        "description": "Prueba de período",
        "days_of_week": ["Sábado"],
        "start_time": "20:00:00",
        "end_time": "21:00:00",
        "status": "draft",
    }
    missing = client.post(
        "/sections/", headers=tokens["admin"], json={**base, "code": "PER-X", "period_name": "NO"}
    )
    assert missing.status_code == 409
    draft = client.post("/sections/", headers=tokens["admin"], json={**base, "code": "PER-Y"})
    assert draft.status_code == 200, draft.text
    assert draft.json()["period_name"] == ""
    with sessions() as db:
        assert db.query(Section).filter_by(code="PER-Y").one().period_id is None
