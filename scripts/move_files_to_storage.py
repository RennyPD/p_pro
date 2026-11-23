"""Move uploaded files from the database to object storage (Fase 4 C, audit M4).

    python -m scripts.move_files_to_storage            # copy and verify each file
    python -m scripts.move_files_to_storage --clear    # also empty the old columns
    python -m scripts.move_files_to_storage --verify   # report only, changes nothing

Uses the storage configured in STORAGE_BACKEND (local folder or S3). Safe to
run several times: files already copied are skipped.
"""

import argparse
import sys

from sqlalchemy.orm import sessionmaker

from app.db.database import engine
from app.services.file_migration import move, verify


def main() -> int:
    parser = argparse.ArgumentParser(description="Traslada los archivos al almacenamiento")
    parser.add_argument("--clear", action="store_true", help="Vacía las columnas ya copiadas")
    parser.add_argument("--verify", action="store_true", help="Solo revisa; no cambia nada")
    args = parser.parse_args()
    factory = sessionmaker(bind=engine)
    if not args.verify:
        report = move(factory, clear=args.clear)
        for table, count in report.moved.items():
            print(f"{table}: {count} copiados, {report.cleared[table]} columnas vaciadas")
    check = verify(factory)
    for table, count in check.pending.items():
        print(f"{table}: {count} pendientes de copiar")
    for item in check.broken:
        print(f"Falta o no coincide: {item}")
    return 1 if check.broken else 0


if __name__ == "__main__":
    sys.exit(main())
