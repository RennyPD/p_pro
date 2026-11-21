"""Copia o restaura la base de datos (SQLite o PostgreSQL) hacia un destino nuevo.

Copia:      python -B -m scripts.backup_database [--output-dir backups]
Restaurar:  python -B -m scripts.backup_database --restore ARCHIVO --destination DESTINO

- SQLite: copia en línea con la API de respaldo; DESTINO es un archivo nuevo.
- PostgreSQL: ``pg_dump`` en formato personalizado (``.dump``); DESTINO es la URL
  de una base vacía. La restauración nunca sobrescribe datos: se niega si la
  base de destino ya tiene tablas, y corre en una sola transacción.

Ambas comprueban el resultado: integridad y claves foráneas en SQLite; lectura
del archivo y número de filas por tabla en PostgreSQL (``--verify-against``
compara la restauración con la base de origen).
"""

import argparse
import os
import shutil
import sqlite3
import subprocess
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL, make_url

from app.db.database import settings

# --- SQLite -------------------------------------------------------------------


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


# --- PostgreSQL ---------------------------------------------------------------


def _libpq(url: str) -> tuple[str, dict[str, str]]:
    """libpq connection string without the password, which goes in PGPASSWORD."""
    parsed: URL = make_url(url)
    if not parsed.drivername.startswith("postgresql"):
        raise ValueError("Se esperaba una URL de PostgreSQL")
    env = dict(os.environ)
    if parsed.password is not None:
        env["PGPASSWORD"] = str(parsed.password)
    plain = parsed.set(drivername="postgresql", password=None)
    return plain.render_as_string(hide_password=False), env


def _tool(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise RuntimeError(f"No se encontró {name}. Instala el cliente de PostgreSQL 16")
    return path


def _run(command: list[str], env: dict[str, str]) -> str:
    result = subprocess.run(command, env=env, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"{Path(command[0]).name} falló: {result.stderr.strip()[:500]}")
    return result.stdout


def row_counts(url: str) -> dict[str, int]:
    """Rows per table of the public schema (verification of a restore)."""
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            tables = inspect(connection).get_table_names()
            return {
                table: connection.execute(text(f'SELECT count(*) FROM "{table}"')).scalar_one()
                for table in sorted(tables)
            }
    finally:
        engine.dispose()


def dump_postgres(url: str, target: Path) -> Path:
    target = target.resolve()
    with target.open("xb"):
        pass
    dsn, env = _libpq(url)
    try:
        _run(
            [
                _tool("pg_dump"),
                "--format=custom",
                "--no-owner",
                "--no-privileges",
                f"--file={target}",
                f"--dbname={dsn}",
            ],
            env,
        )
        listing = _run([_tool("pg_restore"), "--list", str(target)], env)
        if "alembic_version" not in listing:
            raise ValueError("La copia no contiene el esquema de Nexo (falta alembic_version)")
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return target


def restore_postgres(archive: Path, target_url: str) -> dict[str, int]:
    archive = archive.resolve(strict=True)
    if row_counts(target_url):
        raise ValueError(
            "La base de destino ya tiene tablas. Restaura siempre en una base nueva y vacía"
        )
    dsn, env = _libpq(target_url)
    _run(
        [
            _tool("pg_restore"),
            "--no-owner",
            "--no-privileges",
            "--exit-on-error",
            "--single-transaction",
            f"--dbname={dsn}",
            str(archive),
        ],
        env,
    )
    counts = row_counts(target_url)
    if not counts.get("alembic_version"):
        raise ValueError("La restauración no tiene versión de esquema (alembic_version vacía)")
    return counts


def verify_restore(source_url: str, restored_url: str) -> None:
    source, restored = row_counts(source_url), row_counts(restored_url)
    if source != restored:
        different = sorted(
            table
            for table in source.keys() | restored.keys()
            if source.get(table) != restored.get(table)
        )
        raise ValueError("La restauración no coincide con el origen en: " + ", ".join(different))


# --- Entrada ------------------------------------------------------------------


def _stamp() -> str:
    return f"{datetime.now(UTC):%Y%m%d-%H%M%S-%f}Z"


def create_backup(destination: Path | None = None, database_url: str | None = None) -> Path:
    url = database_url or settings.database_url
    target_dir = destination or Path.cwd() / "backups"
    target_dir.mkdir(parents=True, exist_ok=True)
    if url.startswith("sqlite:///"):
        source = Path(url.removeprefix("sqlite:///"))
        if not source.is_absolute():
            source = Path.cwd() / source
        return copy_database(source, target_dir / f"school-{_stamp()}.db")
    if make_url(url).drivername.startswith("postgresql"):
        return dump_postgres(url, target_dir / f"nexo-{_stamp()}.dump")
    raise RuntimeError("Solo se admiten SQLite y PostgreSQL")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, help="Carpeta de las copias (backups/)")
    parser.add_argument("--restore", type=Path, help="Archivo de respaldo de origen")
    parser.add_argument(
        "--destination", help="Archivo nuevo (SQLite) o URL de una base vacía (PostgreSQL)"
    )
    parser.add_argument(
        "--verify-against",
        help="URL de la base de origen para comparar filas por tabla tras restaurar",
    )
    args = parser.parse_args()
    if bool(args.restore) != bool(args.destination):
        parser.error("--restore y --destination deben usarse juntos")
    if not args.restore:
        print(create_backup(args.output_dir))
        return
    if args.destination.startswith("postgresql"):
        counts = restore_postgres(args.restore, args.destination)
        if args.verify_against:
            verify_restore(args.verify_against, args.destination)
        print(f"Restauradas {len(counts)} tablas y {sum(counts.values())} filas")
    else:
        print(copy_database(args.restore, Path(args.destination)))


if __name__ == "__main__":
    main()
