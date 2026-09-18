"""Crea una copia consistente de la base SQLite sin detener la aplicación."""

import sqlite3
from datetime import datetime
from pathlib import Path

from app.db.database import settings


def create_backup(destination: Path | None = None) -> Path:
    if not settings.database_url.startswith("sqlite:///"):
        raise RuntimeError("This local backup command only supports SQLite")
    source = Path(settings.database_url.removeprefix("sqlite:///"))
    if not source.is_absolute():
        source = Path.cwd() / source
    target_dir = destination or Path.cwd() / "backups"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"school-{datetime.now():%Y%m%d-%H%M%S}.db"
    with sqlite3.connect(source) as origin, sqlite3.connect(target) as copy:
        origin.backup(copy)
    return target


if __name__ == "__main__":
    print(create_backup())
