"""Copia o restaura SQLite hacia un archivo nuevo."""

import argparse
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from app.db.database import settings


def copy_database(source: Path, target: Path) -> Path:
    source, target = source.resolve(strict=True), target.resolve()
    if source == target:
        raise ValueError("Selecciona un destino distinto del origen")
    with target.open("xb"):
        pass
    try:
        with (
            closing(sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True)) as origin,
            closing(sqlite3.connect(target)) as copy,
        ):
            origin.backup(copy)
            integrity = copy.execute("PRAGMA integrity_check").fetchall()
            if integrity != [("ok",)] or copy.execute("PRAGMA foreign_key_check").fetchone():
                raise ValueError("La copia no pasó la verificación de integridad y claves foráneas")
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return target


def create_backup(destination: Path | None = None) -> Path:
    if not settings.database_url.startswith("sqlite:///"):
        raise RuntimeError("This local backup command only supports SQLite")
    source = Path(settings.database_url.removeprefix("sqlite:///"))
    if not source.is_absolute():
        source = Path.cwd() / source
    target_dir = destination or Path.cwd() / "backups"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"school-{datetime.now(UTC):%Y%m%d-%H%M%S-%f}Z.db"
    return copy_database(source, target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--restore", type=Path, help="Archivo de respaldo de origen")
    parser.add_argument("--destination", type=Path, help="Archivo nuevo para restaurar")
    args = parser.parse_args()
    if bool(args.restore) != bool(args.destination):
        parser.error("--restore y --destination deben usarse juntos")
    result = copy_database(args.restore, args.destination) if args.restore else create_backup()
    print(result)


if __name__ == "__main__":
    main()
