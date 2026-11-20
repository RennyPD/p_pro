"""Custom roles: permissions decide what, the role scope decides over which records."""

import pytest
from db_support import make_engine
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.Session import get_db
from app.models import Role, Section, Teacher, User
from app.security import hash_password
from main import app
from scripts.seed_demo import seed_demo


@pytest.fixture
def context(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'roles.db'}", connect_args={"timeout": 15})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        seed_demo(db)
        db.commit()

    def override():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override
    with TestClient(app) as client:
        login = client.post(
            "/auth/login", json={"username": "demo.admin", "password": "NexoAdmin2026!"}
        )
        assert login.status_code == 200, login.text
        yield client, sessions, {"Authorization": "Bearer " + login.json()["access_token"]}
    app.dependency_overrides.clear()
    engine.dispose()


def make_role(client, admin, name, scope, permissions):
    role = client.post(
        "/roles/",
        headers=admin,
        json={"name": name, "label": name.title(), "description": name, "scope": scope},
    )
    assert role.status_code == 200, role.text
    saved = client.put(
        f"/access/roles/{role.json()['role_id']}/permissions",
        headers=admin,
        json={"permissions": permissions, "reason": "Rol de prueba"},
    )
    assert saved.status_code == 200, saved.text
    return role.json()["role_id"]


def account(sessions, client, username, role_id, **links):
    with sessions() as db:
        db.add(
            User(
                username=username,
                email=f"{username}@example.com",
                password=hash_password("Prueba2026!"),
                role_id=role_id,
                **links,
            )
        )
        db.commit()
    login = client.post("/auth/login", json={"username": username, "password": "Prueba2026!"})
    assert login.status_code == 200, login.text
    return {"Authorization": "Bearer " + login.json()["access_token"]}


def test_catalog_lists_grouped_permissions_and_scopes(context):
    client, _, admin = context
    catalog = client.get("/access/permissions", headers=admin).json()
    assert {"slug", "module", "label", "description"} <= set(catalog[0])
    assert {item["slug"] for item in catalog} >= {"finance.manage", "roles.manage"}
    assert {s["value"] for s in client.get("/access/scopes", headers=admin).json()} == {
        "institution",
        "sections",
        "own",
        "linked",
    }


def test_cashier_role_reaches_finance_only(context):
    client, sessions, admin = context
    role = make_role(client, admin, "caja", "institution", ["finance.view", "finance.manage"])
    cashier = account(sessions, client, "cajera", role)
    assert client.get("/finance/accounts", headers=cashier).status_code == 200
    me = client.get("/access/me", headers=cashier).json()
    assert me["scope"] == "institution" and "finance.manage" in me["permissions"]
    for method, path in (("POST", "/careers/"), ("GET", "/users/"), ("GET", "/audit/")):
        assert client.request(method, path, headers=cashier, json={}).status_code == 403


def test_section_scope_limits_records_and_blocks_offer_management(context):
    client, sessions, admin = context
    role = make_role(
        client,
        admin,
        "coordinador",
        "sections",
        ["sections.view", "students.view", "attendance.view"],
    )
    with sessions() as db:
        teacher = db.query(Teacher).first()
        mine = {s.section_id for s in db.query(Section).filter_by(teacher_id=teacher.teacher_id)}
        teacher_id = teacher.teacher_id
    coordinator = account(sessions, client, "coordina", role, teacher_id=teacher_id)
    listed = client.get("/sections/", headers=coordinator)
    assert listed.status_code == 200
    assert {item["section_id"] for item in listed.json()} <= mine
    # Even granted by mistake, offer management needs institution scope.
    with sessions() as db:
        assert db.get(Role, role).scope == "sections"
    denied = client.put(
        f"/access/roles/{role}/permissions",
        headers=admin,
        json={"permissions": ["sections.view", "sections.manage"], "reason": "Prueba"},
    )
    assert denied.status_code == 200
    assert client.post("/sections/", headers=coordinator, json={}).status_code == 403


def test_scope_needs_matching_account_links(context):
    client, sessions, admin = context
    role = make_role(client, admin, "auxiliar", "institution", ["students.view"])
    with sessions() as db:
        student_id = db.query(User).filter(User.student_id.is_not(None)).first().student_id
    created = client.post(
        "/users/",
        headers=admin,
        json={
            "username": "aux.estudiante",
            "email": "aux@example.com",
            "password": "Prueba2026!",
            "role_id": role,
            "student_id": student_id,
        },
    )
    assert created.status_code == 422


def test_last_role_manager_cannot_lose_role_management(context):
    client, sessions, admin = context
    with sessions() as db:
        admin_role = db.query(Role).filter_by(name="admin").one().role_id
    removed = client.put(
        f"/access/roles/{admin_role}/permissions",
        headers=admin,
        json={"permissions": ["students.view"], "reason": "Quitar todo"},
    )
    assert removed.status_code == 409
