import sqlite3
from contextlib import closing

import pytest
from db_support import TEST_DATABASE_URL, reset_schema

from scripts.backup_database import copy_database


def test_restore_preserves_data_and_refuses_to_replace_an_existing_destination(tmp_path):
    source = tmp_path / "backup.sqlite"
    target = tmp_path / "restored.sqlite"
    with closing(sqlite3.connect(source)) as database:
        database.executescript(
            """
            CREATE TABLE students(id INTEGER PRIMARY KEY);
            CREATE TABLE charges(student_id INTEGER REFERENCES students(id), cents INTEGER);
            INSERT INTO students VALUES (3);
            INSERT INTO charges VALUES (3, 75000);
            """
        )
    original = source.read_bytes()
    assert copy_database(source, target) == target
    with closing(sqlite3.connect(target)) as database:
        assert database.execute("SELECT cents FROM charges").fetchone() == (75000,)
    with pytest.raises(FileExistsError):
        copy_database(source, target)
    with pytest.raises(ValueError):
        copy_database(source, source)
    assert source.read_bytes() == original


@pytest.mark.skipif(TEST_DATABASE_URL is None, reason="Requiere PostgreSQL (pg_dump/pg_restore)")
def test_postgres_dump_restores_into_a_new_database_with_the_same_rows(tmp_path, monkeypatch):
    """Audit M5: PostgreSQL backups with a tested restore."""
    from alembic.config import Config
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import sessionmaker

    from alembic import command
    from app.db import database
    from scripts.backup_database import (
        create_backup,
        restore_postgres,
        row_counts,
        verify_restore,
    )
    from scripts.seed_demo import seed_demo

    engine = create_engine(TEST_DATABASE_URL)
    reset_schema(engine)
    monkeypatch.setattr(database, "DATABASE_URL", TEST_DATABASE_URL)
    command.upgrade(Config("alembic.ini"), "head")
    with sessionmaker(bind=engine)() as db:
        seed_demo(db)
        db.commit()
    engine.dispose()

    archive = create_backup(tmp_path, database_url=TEST_DATABASE_URL)
    assert archive.suffix == ".dump" and archive.stat().st_size > 0

    source = make_url(TEST_DATABASE_URL)
    restored_name = f"{source.database}_restore_check"
    restored_url = source.set(database=restored_name).render_as_string(hide_password=False)
    admin = create_engine(source.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{restored_name}"'))
        connection.execute(text(f'CREATE DATABASE "{restored_name}"'))
    try:
        counts = restore_postgres(archive, restored_url)
        assert counts["students"] > 0 and counts["alembic_version"] == 1
        verify_restore(TEST_DATABASE_URL, restored_url)
        assert row_counts(restored_url) == row_counts(TEST_DATABASE_URL)
        # A second restore over existing data is refused instead of mixing records.
        with pytest.raises(ValueError, match="base nueva y vacía"):
            restore_postgres(archive, restored_url)
    finally:
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{restored_name}" WITH (FORCE)'))
        admin.dispose()
