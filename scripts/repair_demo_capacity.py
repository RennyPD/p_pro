"""Preview or repair only the known fictitious seed's capacity mismatch.

Requires an explicit database path and --apply to write. Preserves every
selection/grade/attendance, backs up SQLite and records each capacity change.
"""

import argparse
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

SECTIONS = {
    f"{program}-{subject}-A" for program in ("DS", "AC", "MD") for subject in ("101", "102", "201")
}


def preview(db):
    name = db.execute(
        "SELECT institution_name FROM institution_settings WHERE settings_id=1"
    ).fetchone()
    if not name or name[0] != "Instituto Técnico Horizonte":
        raise ValueError("Refusing non-demo institution")
    rows = db.execute(
        "SELECT s.section_id,s.code,s.capacity,p.name,COUNT(*) FROM sections s "
        "JOIN enrollments e ON e.section_id=s.section_id "
        "JOIN academic_periods p ON p.period_id=e.period_id "
        "WHERE e.state='enrolled' GROUP BY s.section_id,p.name HAVING COUNT(*)>s.capacity"
    ).fetchall()
    result = []
    for section_id, code, capacity, period, confirmed in rows:
        if code not in SECTIONS or capacity != 30 or confirmed != 40:
            raise ValueError(f"Unexpected capacity mismatch {code}; requires manual review")
        result.append(
            {
                "section_id": section_id,
                "code": code,
                "period": period,
                "before": capacity,
                "after": 40,
            }
        )
    return result


def repair(database: Path, apply=False):
    database = database.resolve(strict=True)
    uri = database.as_uri() + ("?mode=rw" if apply else "?mode=ro")
    with sqlite3.connect(uri, uri=True, timeout=30, isolation_level=None) as db:
        db.execute("PRAGMA foreign_keys=ON")
        if apply:
            db.execute("BEGIN IMMEDIATE")
        try:
            changes = preview(db)
            result = {
                "database": str(database),
                "applied": False,
                "sections": changes,
                "classrooms": [],
            }
            if not apply or not changes:
                if apply:
                    db.commit()
                return result
            backup = (
                Path(__file__).resolve().parents[1]
                / "backups"
                / f"capacity-before-{uuid4().hex}.db"
            )
            backup.parent.mkdir(exist_ok=True)
            # A separate read connection can back up the committed snapshot while
            # BEGIN IMMEDIATE prevents another writer changing the repair plan.
            with (
                sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as source,
                sqlite3.connect(backup) as target,
            ):
                source.backup(target)
            result["backup"] = str(backup)
            totals_before = {
                table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in ("students", "enrollments", "grades", "attendances")
            }
            now = datetime.now(UTC).replace(tzinfo=None).isoformat(" ")
            for item in changes:
                db.execute(
                    "UPDATE sections SET capacity=40 WHERE section_id=?", (item["section_id"],)
                )
                rooms = db.execute(
                    "SELECT DISTINCT c.classroom_id,c.name,c.capacity FROM classrooms c LEFT JOIN section_meetings m ON m.classroom_id=c.classroom_id WHERE (m.section_id=? OR c.name=(SELECT room FROM sections WHERE section_id=?)) AND c.capacity<40",
                    (item["section_id"], item["section_id"]),
                ).fetchall()
                for room_id, name, capacity in rooms:
                    db.execute("UPDATE classrooms SET capacity=40 WHERE classroom_id=?", (room_id,))
                    result["classrooms"].append(
                        {"classroom_id": room_id, "name": name, "before": capacity, "after": 40}
                    )
                db.execute(
                    "INSERT INTO audit_logs(institution_id,user_id,action,resource,detail,created_at) VALUES(1,NULL,?,?,?,?)",
                    (
                        "demo.capacity.repaired",
                        f"section:{item['section_id']}",
                        f"Corrección autorizada de datos ficticios: {item['code']} cupos 30 -> 40; estudiantes y notas conservados",
                        now,
                    ),
                )
            for table, count in totals_before.items():
                if db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] != count:
                    raise ValueError(f"Unexpected change in {table}")
            if preview(db) or db.execute("PRAGMA foreign_key_check").fetchall():
                raise ValueError("Post-repair integrity failed")
            db.commit()
            result.update(applied=True, preserved_counts=totals_before)
            return result
        except Exception:
            db.rollback()
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(repair(args.database, args.apply), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
