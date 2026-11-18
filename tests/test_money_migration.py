"""Migration 0042 turns FLOAT money into NUMERIC(12, 2) without losing cents."""

from decimal import Decimal

from alembic.config import Config
from db_support import TEST_DATABASE_URL, reset_schema
from sqlalchemy import create_engine, text

from alembic import command
from app.db import database


def test_float_amounts_become_exact_cents(tmp_path, monkeypatch):
    url = TEST_DATABASE_URL or f"sqlite:///{(tmp_path / 'money.db').as_posix()}"
    engine = create_engine(url)
    reset_schema(engine)
    monkeypatch.setattr(database, "DATABASE_URL", url)
    config = Config("alembic.ini")
    command.upgrade(config, "20261118_0041")
    noisy = {"inscripcion": 1250.1000000000001, "laboratorio": 0.1 + 0.2, "carnet": 99.995}
    with engine.begin() as connection:
        for name, amount in noisy.items():
            connection.execute(
                text(
                    "INSERT INTO billing_concepts (name, description, amount, frequency, active) "
                    "VALUES (:name, '', :amount, 'once', TRUE)"
                ),
                {"name": name, "amount": amount},
            )
    command.upgrade(config, "head")
    with engine.connect() as connection:
        rows = dict(connection.execute(text("SELECT name, amount FROM billing_concepts")).all())
    assert Decimal(str(rows["inscripcion"])) == Decimal("1250.10")
    assert Decimal(str(rows["laboratorio"])) == Decimal("0.30")
    # 99.995 is stored as 99.99499999... in binary; either neighbour cent is acceptable.
    assert Decimal(str(rows["carnet"])) in {Decimal("99.99"), Decimal("100.00")}
    engine.dispose()


def test_grade_dates_become_real_dates(tmp_path, monkeypatch):
    url = TEST_DATABASE_URL or f"sqlite:///{(tmp_path / 'grades.db').as_posix()}"
    engine = create_engine(url)
    reset_schema(engine)
    monkeypatch.setattr(database, "DATABASE_URL", url)
    config = Config("alembic.ini")
    command.upgrade(config, "20261118_0043")
    with engine.begin() as connection:
        # Legacy rows only: skip foreign keys instead of building a whole institution.
        if engine.dialect.name == "postgresql":
            connection.execute(text("SET session_replication_role = replica"))
        else:
            connection.execute(text("PRAGMA foreign_keys=OFF"))
        for grade_id, recorded, updated in (
            (1, "2026-09-15", None),
            (2, "15/09/2026", None),
            (3, "2026-09-16T10:00:00", None),
            (4, "sin fecha", "2026-09-20 08:00:00"),
        ):
            connection.execute(
                text(
                    "INSERT INTO grades (grade_id, enrollment_id, grade_value, grade_type, "
                    "date_recorded, status, updated_at) "
                    "VALUES (:id, 1, 80, 'Parcial', :recorded, 'published', :updated)"
                ),
                {"id": grade_id, "recorded": recorded, "updated": updated},
            )
    command.upgrade(config, "head")
    with engine.connect() as connection:
        rows = dict(connection.execute(text("SELECT grade_id, date_recorded FROM grades")).all())
    as_text = {key: str(value)[:10] for key, value in rows.items()}
    assert as_text == {1: "2026-09-15", 2: "2026-09-15", 3: "2026-09-16", 4: "2026-09-20"}
    engine.dispose()
