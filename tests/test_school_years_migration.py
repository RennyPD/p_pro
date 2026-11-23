"""Migration 0056 turns the free-text academic year into school_years rows (Fase 3 B)."""

from alembic.config import Config
from db_support import TEST_DATABASE_URL, reset_schema
from sqlalchemy import create_engine, inspect, text

from alembic import command
from app.db import database


def test_years_are_created_from_period_text_and_restored_on_downgrade(tmp_path, monkeypatch):
    url = TEST_DATABASE_URL or f"sqlite:///{(tmp_path / 'years.db').as_posix()}"
    engine = create_engine(url)
    reset_schema(engine)
    monkeypatch.setattr(database, "DATABASE_URL", url)
    config = Config("alembic.ini")
    command.upgrade(config, "20261123_0055")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO academic_periods (name, start_date, end_date, active, status, "
                "period_type, sequence, academic_year) VALUES "
                "('P1', '2025-08-18', '2025-12-19', FALSE, 'closed', 'trimester', 1, '2025-2026'),"
                "('P2', '2026-01-07', '2026-06-19', TRUE, 'active', 'trimester', 2, ' 2025-2026 '),"
                "('Verano', '2026-07-01', '2026-07-31', FALSE, 'planning', 'annual', 1, '')"
            )
        )

    command.upgrade(config, "20261123_0056")

    columns = {column["name"] for column in inspect(engine).get_columns("academic_periods")}
    assert "school_year_id" in columns and "academic_year" not in columns
    with engine.connect() as connection:
        year = connection.execute(text("SELECT * FROM school_years")).mappings().one()
        assert year["name"] == "2025-2026" and year["period_scheme"] == "trimesters"
        assert str(year["start_date"])[:10] == "2025-08-18"
        assert str(year["end_date"])[:10] == "2026-06-19"
        links = dict(
            connection.execute(text("SELECT name, school_year_id FROM academic_periods")).all()
        )
        assert links == {"P1": year["school_year_id"], "P2": year["school_year_id"], "Verano": None}
        connection.execute(text("UPDATE school_years SET name = '2025-26'"))
        connection.commit()

    command.downgrade(config, "20261123_0055")
    with engine.connect() as connection:
        assert dict(
            connection.execute(text("SELECT name, academic_year FROM academic_periods")).all()
        ) == {
            "P1": "2025-26",
            "P2": "2025-26",
            "Verano": "",
        }
    engine.dispose()
