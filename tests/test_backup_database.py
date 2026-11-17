import sqlite3
from contextlib import closing

import pytest

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
