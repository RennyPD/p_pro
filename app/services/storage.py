"""Uploaded files outside the database (Fase 4 C, audit M4).

Rows keep the file's metadata and a ``storage_key``; the bytes live in a local
folder (development) or an S3-compatible bucket (production). Keys carry the
institution (``inst/<id>/<kind>/<uuid>``) so a bucket can be audited, copied
or deleted per institution.

Files are written before the transaction commits. If the transaction rolls
back, the files it wrote are deleted, so no orphan bytes stay behind.
Downloads keep going through the API, which checks permission and scope.
"""

import hashlib
import logging
import os
import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.db.database import settings
from app.db.tenant import current_tenant

logger = logging.getLogger("nexo.storage")
PENDING = "nexo_stored_files"
UNAVAILABLE = "El archivo no está disponible en este momento. Intenta de nuevo más tarde"


class StorageError(RuntimeError):
    pass


class LocalStorage:
    def __init__(self, root: str):
        self.root = Path(root).resolve()

    def path(self, key: str) -> Path:
        target = (self.root / key).resolve()
        if self.root not in target.parents:
            raise StorageError("Clave de archivo inválida")
        return target

    def put(self, key: str, data: bytes, content_type: str) -> None:
        target = self.path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".partial")
        temporary.write_bytes(data)
        os.replace(temporary, target)

    def get(self, key: str) -> bytes:
        try:
            return self.path(key).read_bytes()
        except FileNotFoundError as exc:
            raise StorageError(f"No existe {key}") from exc

    def delete(self, key: str) -> None:
        self.path(key).unlink(missing_ok=True)

    def check(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        if not os.access(self.root, os.W_OK):
            raise StorageError(f"No se puede escribir en {self.root}")


class S3Storage:
    def __init__(self, client, bucket: str):
        self.client = client
        self.bucket = bucket

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            ServerSideEncryption="AES256",
        )

    def get(self, key: str) -> bytes:
        try:
            return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except Exception as exc:  # botocore raises service-specific classes
            raise StorageError(f"No se pudo leer {key}") from exc

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def check(self) -> None:
        self.client.head_bucket(Bucket=self.bucket)


@lru_cache(maxsize=1)
def backend():
    if settings.storage_backend == "s3":
        import boto3

        client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url or None,
            region_name=settings.s3_region or None,
            aws_access_key_id=settings.s3_access_key_id or None,
            aws_secret_access_key=settings.s3_secret_access_key or None,
        )
        return S3Storage(client, settings.s3_bucket)
    return LocalStorage(settings.storage_dir)


@dataclass(frozen=True)
class Stored:
    key: str
    size: int
    sha256: str


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def store(db: Session, kind: str, data: bytes, content_type: str, institution_id=None) -> Stored:
    """Save ``data`` for the session's institution and remember it until commit."""
    institution = institution_id or current_tenant(db)
    if institution is None:
        raise StorageError("No se puede guardar un archivo sin institución")
    key = f"inst/{institution}/{kind}/{uuid.uuid4().hex}"
    db.connection()  # begin the transaction now, so its end always cleans up
    try:
        backend().put(key, data, content_type)
    except StorageError:
        raise
    except Exception as exc:
        logger.exception("storage_put_failed", extra={"key": key})
        raise HTTPException(503, UNAVAILABLE) from exc
    db.info.setdefault(PENDING, []).append(key)
    return Stored(key=key, size=len(data), sha256=digest(data))


def read(key: str | None, legacy: bytes | None) -> bytes:
    """The file's bytes: from storage, or from the old column until it is moved."""
    if key:
        try:
            return backend().get(key)
        except StorageError as exc:
            logger.error("storage_get_failed", extra={"key": key})
            raise HTTPException(503, UNAVAILABLE) from exc
    if legacy is None:
        raise HTTPException(404, "Archivo no encontrado")
    return legacy


@event.listens_for(Session, "after_commit")
def _keep(session: Session) -> None:
    session.info.pop(PENDING, None)


@event.listens_for(Session, "after_transaction_end")
def _discard(session: Session, transaction) -> None:
    """Rolled back, or closed without commit: delete what this transaction wrote."""
    if transaction.parent is not None:
        return  # savepoints and subtransactions: the outer transaction decides
    for key in session.info.pop(PENDING, []):
        try:
            backend().delete(key)
        except Exception:
            logger.warning("storage_orphan", extra={"key": key})
