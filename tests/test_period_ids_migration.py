"""Migration 0054 links sections, enrollments and cart items to periods by id (B5)."""

from alembic.config import Config
from db_support import TEST_DATABASE_URL, reset_schema
from sqlalchemy import create_engine, inspect, text

from alembic import command
from app.db import database


def columns(engine, table):
    return {column["name"] for column in inspect(engine).get_columns(table)}


def test_periods_are_linked_by_id_and_legacy_names_get_a_closed_period(tmp_path, monkeypatch):
    url = TEST_DATABASE_URL or f"sqlite:///{(tmp_path / 'periods.db').as_posix()}"
    engine = create_engine(url)
    reset_schema(engine)
    monkeypatch.setattr(database, "DATABASE_URL", url)
    config = Config("alembic.ini")
    command.upgrade(config, "20261122_0053")
    with engine.begin() as connection:
        # Legacy rows only: skip foreign keys instead of building a whole institution.
        if engine.dialect.name == "postgresql":
            connection.execute(text("SET session_replication_role = replica"))
        else:
            connection.execute(text("PRAGMA foreign_keys=OFF"))
        connection.execute(
            text(
                "INSERT INTO academic_periods (name, start_date, end_date, active, "
                "status, period_type, sequence, academic_year) VALUES "
                "('2026-1', '2026-01-10', '2026-05-30', TRUE, 'active', 'semester', 1, '2026')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO sections (section_id, code, description, teacher_id, subject_id, "
                "days_of_week, start_time, end_time, capacity, room, modality, status, "
                "minimum_capacity, period_name) VALUES "
                "(1, 'S-1', 'Con período', 1, 1, 'Lunes', '08:00', '09:00', 30, 'A', "
                "'in_person', 'active', 1, '2026-1'), "
                "(2, 'S-2', 'Borrador', 1, 1, 'Martes', '08:00', '09:00', 30, 'A', "
                "'in_person', 'draft', 1, '')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO enrollments (enrollment_id, student_id, section_id, enrollment_date, "
                "state, period) VALUES "
                "(1, 1, 1, '2026-02-01 10:00:00', 'enrolled', '2026-1'), "
                "(2, 1, 1, '2019-03-01 10:00:00', 'completed', 'LEGADO-2019')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO course_selection_cart (cart_item_id, student_id, section_id, period, "
                "created_at) VALUES (1, 1, 1, '2026-1', '2026-01-05 09:00:00')"
            )
        )

    command.upgrade(config, "20261123_0054")

    for table in ("sections", "enrollments", "course_selection_cart"):
        assert "period_id" in columns(engine, table)
    assert "period_name" not in columns(engine, "sections")
    assert "period" not in columns(engine, "enrollments")
    with engine.connect() as connection:
        current = connection.execute(
            text("SELECT period_id FROM academic_periods WHERE name='2026-1'")
        ).scalar()
        legacy = connection.execute(
            text("SELECT period_id, status, active FROM academic_periods WHERE name='LEGADO-2019'")
        ).one()
        assert legacy.status == "closed" and not legacy.active
        assert dict(
            connection.execute(text("SELECT enrollment_id, period_id FROM enrollments")).all()
        ) == {1: current, 2: legacy.period_id}
        assert dict(
            connection.execute(text("SELECT section_id, period_id FROM sections")).all()
        ) == {1: current, 2: None}
        cart = connection.execute(text("SELECT period_id FROM course_selection_cart")).scalar()
        assert cart == current
        # Renaming the period no longer breaks any link.
        connection.execute(
            text("UPDATE academic_periods SET name='2026-I' WHERE period_id=:id"), {"id": current}
        )
        connection.commit()

    command.downgrade(config, "20261122_0053")
    with engine.connect() as connection:
        assert dict(
            connection.execute(text("SELECT section_id, period_name FROM sections")).all()
        ) == {
            1: "2026-I",
            2: "",
        }
        assert dict(
            connection.execute(text("SELECT enrollment_id, period FROM enrollments")).all()
        ) == {
            1: "2026-I",
            2: "LEGADO-2019",
        }
    engine.dispose()
