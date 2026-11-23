"""Copy files kept in binary columns to object storage (Fase 4 C, audit M4).

Each file is written, read back and compared by SHA-256 before its row points
to the storage key. With ``clear`` the old column is emptied afterwards; the
columns themselves are dropped by a later migration once ``verify`` reports
nothing pending.
"""

from dataclasses import dataclass, field

from sqlalchemy.orm import Session, sessionmaker

from app.models.finance_model import TransferBatch, TransferRequest
from app.models.operations_model import StudentDocument, SubmissionAttachment
from app.services import storage


@dataclass(frozen=True)
class FileColumns:
    model: type
    kind: str
    binary: str
    key: str
    size: str
    sha: str
    mime: str


COLUMNS = (
    FileColumns(StudentDocument, "documents", "content", "storage_key", "size_bytes", "sha256", "mime_type"),
    FileColumns(SubmissionAttachment, "submissions", "content", "storage_key", "size_bytes", "sha256", "mime_type"),
    FileColumns(TransferBatch, "transfers", "proof", "proof_key", "proof_size", "proof_sha256", "proof_type"),
    FileColumns(TransferRequest, "transfers", "proof", "proof_key", "proof_size", "proof_sha256", "proof_type"),
)  # fmt: skip


@dataclass
class Report:
    moved: dict[str, int] = field(default_factory=dict)
    cleared: dict[str, int] = field(default_factory=dict)
    pending: dict[str, int] = field(default_factory=dict)
    broken: list[str] = field(default_factory=list)


def move(factory: sessionmaker, clear: bool = False, batch: int = 50) -> Report:
    report = Report()
    for columns in COLUMNS:
        table = columns.model.__tablename__
        moved = cleared = 0
        while True:
            with factory() as db:
                rows = _pending(db, columns).limit(batch).all()
                if not rows:
                    break
                for row in rows:
                    data = getattr(row, columns.binary)
                    stored = storage.store(
                        db, columns.kind, data, getattr(row, columns.mime), row.institution_id
                    )
                    if storage.digest(storage.backend().get(stored.key)) != stored.sha256:
                        raise storage.StorageError(f"La copia de {table} no coincide")
                    setattr(row, columns.key, stored.key)
                    setattr(row, columns.size, stored.size)
                    setattr(row, columns.sha, stored.sha256)
                    moved += 1
                db.commit()
        if clear:
            cleared = _clear(factory, columns)
        report.moved[table], report.cleared[table] = moved, cleared
    return report


def _pending(db: Session, columns: FileColumns):
    model = columns.model
    return db.query(model).filter(
        getattr(model, columns.key).is_(None), getattr(model, columns.binary).is_not(None)
    )


def _clear(factory: sessionmaker, columns: FileColumns) -> int:
    """Empty the old column only where the stored copy still matches."""
    model, count = columns.model, 0
    with factory() as db:
        rows = db.query(model).filter(
            getattr(model, columns.key).is_not(None), getattr(model, columns.binary).is_not(None)
        )
        for row in rows:
            data = storage.backend().get(getattr(row, columns.key))
            if storage.digest(data) == getattr(row, columns.sha):
                setattr(row, columns.binary, None)
                count += 1
        db.commit()
    return count


def verify(factory: sessionmaker) -> Report:
    """Files still only in the database, and stored files missing or altered."""
    report = Report()
    for columns in COLUMNS:
        model, table = columns.model, columns.model.__tablename__
        with factory() as db:
            report.pending[table] = _pending(db, columns).count()
            for row in db.query(model).filter(getattr(model, columns.key).is_not(None)):
                key = getattr(row, columns.key)
                try:
                    intact = storage.digest(storage.backend().get(key)) == getattr(row, columns.sha)
                except storage.StorageError:
                    intact = False
                if not intact:
                    report.broken.append(f"{table}: {key}")
    return report
