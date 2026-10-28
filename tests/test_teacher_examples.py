import sqlite3
from collections import Counter
from pathlib import Path

import pytest

from app.schemas.teacher_schema import TeacherCreate
from scripts import seed_teacher_examples as loader


def test_all_teacher_fields_and_scenarios_have_examples():
    examples = loader.teacher_examples()
    assert len(examples) == 12
    assert Counter(item["employment_type"] for item in examples) == {
        "full_time": 3,
        "part_time": 3,
        "adjunct": 3,
        "substitute": 3,
    }
    assert sum(item["active"] for item in examples) == 10
    assert len({item["email"] for item in examples}) == 12
    for item in examples:
        TeacherCreate.model_validate(item)
        assert set(item) == set(TeacherCreate.model_fields)
        assert all(value is not None and value != "" for value in item.values())
        assert item["email"].endswith("@example.com")


def create_database(path):
    example = loader.teacher_examples()[0]
    with sqlite3.connect(path) as db:
        columns = ",".join(f'"{column}"' for column in example)
        db.execute(
            f"CREATE TABLE teachers (teacher_id INTEGER PRIMARY KEY, {columns}, UNIQUE(email))"
        )
        db.execute(
            "INSERT INTO teachers (teacher_id,first_name,email) VALUES (1,'Anterior','anterior@example.com')"
        )
        db.execute("CREATE TABLE preserved (id INTEGER PRIMARY KEY, note TEXT)")
        db.execute("INSERT INTO preserved VALUES (1,'No modificar')")


def test_loading_is_backed_up_additive_and_idempotent(tmp_path, monkeypatch):
    database = tmp_path / "school.db"
    create_database(database)
    monkeypatch.setattr(loader, "BACKUP_DIRECTORY", tmp_path / "backups")
    assert loader.seed(database)["to_insert"] == 12
    result = loader.seed(database, apply=True)
    assert result["total_teachers"] == 13
    assert Path(result["backup"]).is_file()
    with sqlite3.connect(result["backup"]) as db:
        assert db.execute("SELECT COUNT(*) FROM teachers").fetchone()[0] == 1
    with sqlite3.connect(database) as db:
        assert (
            db.execute("SELECT first_name FROM teachers WHERE teacher_id=1").fetchone()[0]
            == "Anterior"
        )
        assert db.execute("SELECT * FROM preserved").fetchall() == [(1, "No modificar")]
        db.execute(
            "UPDATE teachers SET specialty='Edición conservada' WHERE employee_code='DEMO-DOC-001'"
        )
    assert loader.seed(database, apply=True)["to_insert"] == 0
    with sqlite3.connect(database) as db:
        assert (
            db.execute(
                "SELECT specialty FROM teachers WHERE employee_code='DEMO-DOC-001'"
            ).fetchone()[0]
            == "Edición conservada"
        )


def test_existing_identity_conflict_prevents_any_insert(tmp_path):
    database = tmp_path / "school.db"
    create_database(database)
    with sqlite3.connect(database) as db:
        db.execute("UPDATE teachers SET employee_code='DEMO-DOC-001'")
    with pytest.raises(ValueError, match="conflicto"):
        loader.seed(database, apply=True)
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT COUNT(*) FROM teachers").fetchone()[0] == 1
