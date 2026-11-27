"""All the data of one institution: export and deletion (Fase 5, step G4).

Used by the institution's full export (portability, leaving Nexo), by the
final deletion 90 days after a cancellation, and by the demo's nightly reset.
"""

import csv
import io
import logging
import zipfile
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import Base
from app.db.tenant import tenant_bypass

logger = logging.getLogger("nexo.institution_data")

# Global tables that only point to an institution (kept by the demo reset).
GLOBAL_WITH_INSTITUTION = {"institutions", "subscriptions", "legal_acceptances", "billing_events"}
# Never exported: credentials, session tokens and emails with private links.
SECRET_TABLES = {"refresh_tokens", "one_time_tokens", "email_outbox", "write_locks"}
SECRET_COLUMNS = {
    "users": {"password", "mfa_secret", "mfa_pending_secret", "mfa_last_step", "session_version"},
    "payment_gateway_configs": {"secrets"},
    "fiscal_profiles": {"ecf_secrets"},
    "submission_attachments": {"content"},
    "student_documents": {"content"},
    "transfer_batches": {"proof"},
    "transfer_requests": {"proof"},
}


def tenant_tables():
    """Tables of the institution, children first (safe deletion order)."""
    return [
        table
        for table in reversed(Base.metadata.sorted_tables)
        if "institution_id" in table.columns and table.name not in GLOBAL_WITH_INSTITUTION
    ]


def stored_files(db: Session, institution_id: int) -> list[tuple[str, str, str]]:
    """(kind, storage key, file name) of every uploaded file of the institution."""
    from app.services.file_migration import COLUMNS

    files = []
    for columns in COLUMNS:
        model = columns.model
        name_column = getattr(model, "filename", None)
        rows = (
            db.query(
                getattr(model, columns.key),
                name_column if name_column is not None else getattr(model, columns.key),
            )
            .filter(
                model.institution_id == institution_id, getattr(model, columns.key).is_not(None)
            )
            .execution_options(**tenant_bypass())
            .all()
        )
        files += [(columns.kind, key, str(name)) for key, name in rows]
    return files


def delete_institution_rows(db: Session, institution_id: int) -> int:
    """Delete every row and uploaded file of one institution (never other ones)."""
    from app.services import storage

    for _kind, key, _name in stored_files(db, institution_id):
        try:
            storage.backend().delete(key)
        except Exception:
            logger.warning("file_not_deleted", extra={"key": key})
    deleted = 0
    for table in tenant_tables():
        deleted += db.execute(
            table.delete().where(table.c.institution_id == institution_id)
        ).rowcount
    db.flush()
    return deleted


def cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "sí" if value else "no"
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    return str(value)


def export_zip(db: Session, institution_id: int) -> bytes:
    """One CSV per table (UTF-8 with BOM, opens in Excel) and the uploaded files."""
    from app.services import storage

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        summary = []
        for table in sorted(tenant_tables(), key=lambda t: t.name):
            if table.name in SECRET_TABLES:
                continue
            hidden = SECRET_COLUMNS.get(table.name, set())
            columns = [column for column in table.columns if column.name not in hidden]
            rows = db.execute(
                select(*columns).where(table.c.institution_id == institution_id)
            ).all()
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow([column.name for column in columns])
            writer.writerows([cell(value) for value in row] for row in rows)
            archive.writestr(f"datos/{table.name}.csv", "﻿" + buffer.getvalue())
            summary.append(f"{table.name}: {len(rows)} filas")
        files = stored_files(db, institution_id)
        for kind, key, name in files:
            try:
                archive.writestr(
                    f"archivos/{kind}/{key.rsplit('/', 1)[-1]}-{name}", storage.backend().get(key)
                )
            except Exception:
                summary.append(f"No se pudo incluir el archivo {key}")
        archive.writestr(
            "LEEME.txt",
            "Exportación de Nexo\n"
            f"Generada: {datetime.now().isoformat(timespec='seconds')}\n\n"
            "datos/: un archivo CSV por tabla (UTF-8). archivos/: documentos y comprobantes subidos.\n"
            "No incluye contraseñas, segundos factores, sesiones ni claves de pasarelas.\n\n"
            + "\n".join(summary)
            + f"\narchivos: {len(files)}\n",
        )
    return output.getvalue()
