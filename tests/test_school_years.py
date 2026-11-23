"""School years and generated periods (Fase 3, block B)."""

from datetime import date

from test_institution_type import settings_payload
from test_write_audit import demo, entries  # noqa: F401  (demo is a shared fixture)

from app.models.configuration_model import AcademicPeriod, SchoolYear
from app.services.school_years import split_dates


def test_split_dates_covers_the_year_without_gaps():
    ranges = split_dates(date(2026, 8, 17), date(2027, 6, 18), 4)
    assert ranges[0][0] == date(2026, 8, 17) and ranges[-1][1] == date(2027, 6, 18)
    for (_, end), (start, _) in zip(ranges, ranges[1:]):
        assert (start - end).days == 1
    lengths = [(end - start).days for start, end in ranges]
    assert max(lengths) - min(lengths) <= 1


def test_school_generates_four_minerd_periods(demo):  # noqa: F811
    client, sessions, tokens = demo
    admin = tokens["admin"]
    with sessions() as db:
        # A school: the demo's university careers would block the switch.
        from app.models import Career

        for career in db.query(Career):
            career.academic_level = "secondary"
        db.commit()
    switched = client.put(
        "/configuration/institution",
        headers=admin,
        json=settings_payload(client, admin, institution_type="school"),
    )
    assert switched.status_code == 200, switched.text
    year = client.post(
        "/school-years/",
        headers=admin,
        json={"name": "2026-2027", "start_date": "2026-08-17", "end_date": "2027-06-18"},
    )
    assert year.status_code == 200, year.text
    assert year.json()["period_scheme"] == "quarters"
    year_id = year.json()["school_year_id"]
    generated = client.post(f"/school-years/{year_id}/generate-periods", headers=admin)
    assert generated.status_code == 200, generated.text
    periods = generated.json()
    assert [p["name"] for p in periods] == [f"Período {n} · 2026-2027" for n in range(1, 5)]
    assert {p["period_type"] for p in periods} == {"quarter"}
    assert all(p["academic_year"] == "2026-2027" and p["status"] == "planning" for p in periods)
    assert periods[0]["start_date"] == "2026-08-17" and periods[-1]["end_date"] == "2027-06-18"
    again = client.post(f"/school-years/{year_id}/generate-periods", headers=admin)
    assert again.status_code == 409
    listed = client.get("/school-years/", headers=admin)
    assert listed.headers["X-Total-Count"] == "1"
    assert listed.json()[0]["period_count"] == 4
    # Periods must stay inside the year; the scheme is fixed once it has periods.
    shrink = client.patch(
        f"/school-years/{year_id}", headers=admin, json={"end_date": "2027-05-01"}
    )
    assert shrink.status_code == 409
    scheme = client.patch(
        f"/school-years/{year_id}", headers=admin, json={"period_scheme": "semesters"}
    )
    assert scheme.status_code == 409
    assert client.delete(f"/school-years/{year_id}", headers=admin).status_code == 409
    for action in ("school_year.created", "school_year.periods_generated"):
        assert entries(sessions, action, f"school-year:{year_id}")


def test_university_default_and_permissions(demo):  # noqa: F811
    client, _sessions, tokens = demo
    payload = {"name": "2027", "start_date": "2027-01-11", "end_date": "2027-12-10"}
    assert client.post("/school-years/", headers=tokens["docente"], json=payload).status_code == 403
    year = client.post("/school-years/", headers=tokens["admin"], json=payload).json()
    assert year["period_scheme"] == "semesters"
    duplicate = client.post("/school-years/", headers=tokens["admin"], json=payload)
    assert duplicate.status_code == 409
    renamed = client.patch(
        f"/school-years/{year['school_year_id']}", headers=tokens["admin"], json={"name": "2027-A"}
    )
    assert renamed.status_code == 200 and renamed.json()["name"] == "2027-A"
    deleted = client.delete(f"/school-years/{year['school_year_id']}", headers=tokens["admin"])
    assert deleted.status_code == 200


def test_period_form_links_or_creates_the_year_by_name(demo):  # noqa: F811
    client, sessions, tokens = demo
    admin = tokens["admin"]
    created = client.post(
        "/periods/",
        headers=admin,
        json={
            "name": "2028-1",
            "start_date": "2028-01-10",
            "end_date": "2028-05-20",
            "academic_year": "2028",
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["academic_year"] == "2028"
    second = client.post(
        "/periods/",
        headers=admin,
        json={
            "name": "2028-2",
            "start_date": "2028-08-10",
            "end_date": "2028-12-15",
            "academic_year": "2028",
            "sequence": 2,
        },
    )
    assert second.status_code == 200, second.text
    with sessions() as db:
        years = db.query(SchoolYear).filter_by(name="2028").all()
        assert len(years) == 1
        assert (years[0].start_date, years[0].end_date) == (date(2028, 1, 10), date(2028, 12, 15))
        assert years[0].period_count == 2
        # Renaming the year renames it for every period: they point to it by id.
        years[0].name = "2028 lectivo"
        db.commit()
        assert {
            p.academic_year
            for p in db.query(AcademicPeriod).filter_by(school_year_id=years[0].school_year_id)
        } == {"2028 lectivo"}
    found = client.get("/periods/?q=lectivo", headers=admin).json()
    assert {p["name"] for p in found} == {"2028-1", "2028-2"}
    moved = client.patch(
        f"/periods/{created.json()['period_id']}", headers=admin, json={"academic_year": ""}
    )
    assert moved.status_code == 200 and moved.json()["school_year_id"] is None
