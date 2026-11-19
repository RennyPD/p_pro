"""Section rooms: registered classrooms only, no double booking (drafts reserve too)."""

from datetime import date

import pytest
from db_support import make_engine
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.Session import get_db
from app.models import AcademicPeriod, Classroom, Section
from main import app
from scripts.seed_demo import seed_demo


@pytest.fixture
def context(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'rooms.db'}", connect_args={"timeout": 15})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        seed_demo(db)
        source = db.query(Section).filter_by(code="PROG-101-A").one()
        db.add_all(
            [
                Classroom(name="Aula Norte", capacity=40, location="Edificio N"),
                Classroom(name="Aula Pequeña", capacity=5),
                Classroom(name="Aula Vieja", capacity=40, active=False),
                AcademicPeriod(
                    name="ROOMS-2030",
                    start_date=date(2030, 1, 1),
                    end_date=date(2030, 6, 30),
                    status="active",
                ),
            ]
        )
        db.commit()
        base = {
            "teacher_id": source.teacher_id,
            "subject_id": source.subject_id,
            "period_name": "ROOMS-2030",
        }

    def override():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override
    with TestClient(app) as client:
        login = client.post(
            "/auth/login", json={"username": "demo.admin", "password": "NexoAdmin2026!"}
        )
        assert login.status_code == 200, login.text
        headers = {"Authorization": "Bearer " + login.json()["access_token"]}
        yield client, headers, base
    app.dependency_overrides.clear()
    engine.dispose()


def section(base, code, **values):
    return {
        **base,
        "code": code,
        "description": code,
        "days_of_week": ["Sábado"],
        "start_time": "08:00:00",
        "end_time": "10:00:00",
        "capacity": 30,
        "status": "draft",
        **values,
    }


def test_a_draft_reserves_its_room_and_blocks_an_overlapping_section(context):
    client, headers, base = context
    first = client.post(
        "/sections/", headers=headers, json=section(base, "ROOM-A", room="Aula Norte")
    )
    assert first.status_code == 200, first.text
    clash = client.post(
        "/sections/",
        headers=headers,
        json=section(base, "ROOM-B", room="aula norte", start_time="09:00:00", end_time="11:00:00"),
    )
    assert clash.status_code == 409
    assert "ocupada" in clash.json()["detail"] and "ROOM-A" in clash.json()["detail"]
    later = client.post(
        "/sections/",
        headers=headers,
        json=section(base, "ROOM-C", room="Aula Norte", start_time="10:00:00", end_time="12:00:00"),
    )
    assert later.status_code == 200, later.text


def test_rooms_must_be_registered_active_and_large_enough(context):
    client, headers, base = context
    for room, fragment in (
        ("Aula Inventada", "no está registrada"),
        ("Aula Vieja", "retirada"),
        ("Aula Pequeña", "plazas"),
    ):
        response = client.post(
            "/sections/", headers=headers, json=section(base, f"R-{room[-4:]}", room=room)
        )
        assert response.status_code in {409, 422}, response.text
        assert fragment in response.json()["detail"]


def test_publishing_requires_a_room_unless_virtual(context):
    client, headers, base = context
    draft = client.post("/sections/", headers=headers, json=section(base, "NO-ROOM"))
    assert draft.status_code == 200, draft.text
    published = client.patch(
        f"/sections/{draft.json()['section_id']}", headers=headers, json={"status": "published"}
    )
    assert published.status_code == 409, published.text
    assert "Asigna un aula" in published.json()["detail"]
    virtual = client.post(
        "/sections/",
        headers=headers,
        json=section(base, "ONLINE", status="published", modality="virtual"),
    )
    assert virtual.status_code == 200, virtual.text


def test_availability_lists_each_classroom_with_its_status(context):
    client, headers, base = context
    assert (
        client.post(
            "/sections/", headers=headers, json=section(base, "HOLD", room="Aula Norte")
        ).status_code
        == 200
    )
    params = {
        "days": "Sábado",
        "start_time": "09:00",
        "end_time": "09:30",
        "capacity": 30,
        "period_name": "ROOMS-2030",
    }
    rooms = {
        item["name"]: item
        for item in client.get(
            "/scheduling/classrooms/availability", headers=headers, params=params
        ).json()
    }
    assert rooms["Aula Norte"]["status"] == "busy" and "HOLD" in rooms["Aula Norte"]["detail"]
    assert rooms["Aula Pequeña"]["status"] == "small"
    assert rooms["Aula Vieja"]["status"] == "retired"
    hold_id = next(
        item["section_id"]
        for item in client.get("/sections/", headers=headers).json()
        if item["code"] == "HOLD"
    )
    own = client.get(
        "/scheduling/classrooms/availability",
        headers=headers,
        params={**params, "section_id": hold_id},
    ).json()
    assert next(item for item in own if item["name"] == "Aula Norte")["status"] == "available"
