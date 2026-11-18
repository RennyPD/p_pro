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
