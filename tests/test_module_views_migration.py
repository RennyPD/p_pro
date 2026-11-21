"""Migration 0048 turns per-account read-only modules into role permissions (B4)."""

from alembic.config import Config
from db_support import TEST_DATABASE_URL, reset_schema
from sqlalchemy import create_engine, inspect, text

from alembic import command
from app.db import database


def test_account_modules_become_view_permissions_of_the_role(tmp_path, monkeypatch):
    url = TEST_DATABASE_URL or f"sqlite:///{(tmp_path / 'modules.db').as_posix()}"
    engine = create_engine(url)
    reset_schema(engine)
    monkeypatch.setattr(database, "DATABASE_URL", url)
    config = Config("alembic.ini")
    command.upgrade(config, "20261120_0047")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO roles (role_id, name, description, scope) VALUES "
                "(1, 'admin', 'Administración', 'institution'), "
                "(2, 'observador', 'Consulta', 'institution'), "
                "(3, 'otro', 'Sin módulos', 'institution')"
            )
        )
        # Earlier migrations already seed the permission catalog (catalog in use).
        for user_id, role_id, modules in (
            (1, 1, None),
            (2, 2, '["students", "careers", "periods"]'),
            (3, 3, "[]"),
        ):
            connection.execute(
                text(
                    "INSERT INTO users (user_id, username, email, password, role_id, module_views) "
                    "VALUES (:id, :name, :email, 'x', :role, :modules)"
                ),
                {
                    "id": user_id,
                    "name": f"cuenta{user_id}",
                    "email": f"cuenta{user_id}@example.com",
                    "role": role_id,
                    "modules": modules,
                },
            )

    command.upgrade(config, "20261121_0048")

    with engine.connect() as connection:
        grants = {
            (role, slug)
            for role, slug in connection.execute(
                text(
                    "SELECT rp.role_id, p.slug FROM role_permissions rp "
                    "JOIN permissions p ON p.permission_id = rp.permission_id"
                )
            )
        }
    assert {(2, "students.view"), (2, "programs.view"), (1, "programs.view")} <= grants
    assert not {slug for role, slug in grants if role == 2} & {"students.manage", "programs.manage"}
    assert not [slug for role, slug in grants if role == 3]
    assert "module_views" not in {c["name"] for c in inspect(engine).get_columns("users")}

    command.downgrade(config, "20261120_0047")
    assert "module_views" in {c["name"] for c in inspect(engine).get_columns("users")}
    engine.dispose()
