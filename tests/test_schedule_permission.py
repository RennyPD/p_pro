"""Schedule blocks are edited with the schedule.manage permission, not by role name."""

from datetime import time

import pytest
from db_support import make_engine
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.Session import get_db
from app.models import Permission, Role, RolePermission, Section, SectionMeeting, Teacher
from main import app
from scripts.seed_demo import seed_demo

PASSWORDS = {"demo.admin": "NexoAdmin2026!", "demo.docente": "NexoDocente2026!"}


@pytest.fixture
def context(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'schedule.db'}", connect_args={"timeout": 15})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        seed_demo(db)
        own = db.query(Section).filter_by(code="PROG-101-A").one()
        other_teacher = Teacher(
            first_name="Otra",
            last_name="Docente",
            email="otra.docente@example.com",
            telephone="8095550199",
            specialty="Matemática",
            address="Ficticia",
        )
        db.add(other_teacher)
        db.flush()
        foreign = Section(
            code="AJENA-01",
            description="Sección de otro docente",
            teacher_id=other_teacher.teacher_id,
            subject_id=own.subject_id,
            days_of_week="Viernes",
            start_time=time(18),
            end_time=time(19),
            capacity=20,
            period_name=own.period_name,
            status="active",
        )
        db.add(foreign)
        db.flush()
        meeting = SectionMeeting(
            section_id=own.section_id,
            day_of_week="Sábado",
            start_time=time(8),
            end_time=time(9),
            modality="virtual",
            virtual_url="https://aula.example.com/prog",
        )
        db.add(meeting)
        db.commit()
        ids = {
            "own": own.section_id,
            "foreign": foreign.section_id,
            "meeting": meeting.meeting_id,
        }

    def override():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override
    with TestClient(app) as client:
        headers = {}
        for username, password in PASSWORDS.items():
            login = client.post("/auth/login", json={"username": username, "password": password})
            assert login.status_code == 200, login.text
            headers[username] = {"Authorization": "Bearer " + login.json()["access_token"]}
        yield client, sessions, headers, ids
    app.dependency_overrides.clear()
    engine.dispose()


def block(section_id, day="Sábado", start="14:00:00", end="15:00:00"):
    return {
        "section_id": section_id,
        "day_of_week": day,
        "start_time": start,
        "end_time": end,
        "modality": "virtual",
        "virtual_url": "https://aula.example.com/sesion",
    }


def grant(sessions, role_name, *slugs):
    with sessions() as db:
        role = db.query(Role).filter_by(name=role_name).one()
        for slug in slugs:
            permission = db.query(Permission).filter_by(slug=slug).one_or_none()
            if permission is None:
                permission = Permission(slug=slug, description=slug)
                db.add(permission)
                db.flush()
            db.add(RolePermission(role_id=role.role_id, permission_id=permission.permission_id))
        db.commit()


def test_teacher_role_alone_cannot_edit_blocks_of_own_section(context):
    client, _, headers, ids = context
    teacher = headers["demo.docente"]
    meeting = f"/scheduling/meetings/{ids['meeting']}"

    created = client.post("/scheduling/meetings", headers=teacher, json=block(ids["own"]))
    updated = client.put(meeting, headers=teacher, json=block(ids["own"], start="09:00:00"))
    deleted = client.delete(meeting, headers=teacher)

    for response in (created, updated, deleted):
        assert response.status_code == 403, response.text
    # Reading the schedule of an assigned section is still allowed.
    listed = client.get(f"/scheduling/sections/{ids['own']}/meetings", headers=teacher)
    assert listed.status_code == 200
    assert [item["meeting_id"] for item in listed.json()] == [ids["meeting"]]


def test_unconfigured_admin_keeps_editing_blocks(context):
    client, _, headers, ids = context
    response = client.post(
        "/scheduling/meetings", headers=headers["demo.admin"], json=block(ids["foreign"])
    )
    assert response.status_code == 200, response.text


def test_configured_permission_decides_and_scope_still_applies(context):
    client, sessions, headers, ids = context
    # Once permissions are configured, the admin role needs the grant too.
    grant(sessions, "admin", "academic.manage")
    denied = client.post(
        "/scheduling/meetings", headers=headers["demo.admin"], json=block(ids["foreign"])
    )
    assert denied.status_code == 403
    assert denied.json()["detail"] == "Te falta el permiso: schedule.manage"

    grant(sessions, "teacher", "schedule.manage")
    teacher = headers["demo.docente"]
    own = client.post("/scheduling/meetings", headers=teacher, json=block(ids["own"]))
    assert own.status_code == 200, own.text
    foreign = client.post("/scheduling/meetings", headers=teacher, json=block(ids["foreign"]))
    assert foreign.status_code == 403
    assert foreign.json()["detail"] == "La sección está fuera de tu ámbito académico"

    grant(sessions, "admin", "schedule.manage")
    allowed = client.post(
        "/scheduling/meetings", headers=headers["demo.admin"], json=block(ids["foreign"])
    )
    assert allowed.status_code == 200, allowed.text
