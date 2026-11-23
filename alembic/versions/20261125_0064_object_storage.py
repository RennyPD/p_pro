"""Uploaded files in object storage (Fase 4 C, audit M4).

Adds the storage key, size and SHA-256 to the four tables that kept files in
binary columns, and makes those columns optional. New uploads go to storage;
``python -m scripts.move_files_to_storage`` copies the existing ones. The
binary columns are dropped by a later migration, once every file is copied.

Revision ID: 20261125_0064
Revises: 20261124_0063
"""

import sqlalchemy as sa

from alembic import op

revision = "20261125_0064"
down_revision = "20261124_0063"
branch_labels = None
depends_on = None

TABLES = {
    # table: (binary column, key column, size column, digest column)
    "submission_attachments": ("content", "storage_key", "size_bytes", "sha256"),
    "student_documents": ("content", "storage_key", "size_bytes", "sha256"),
    "transfer_batches": ("proof", "proof_key", "proof_size", "proof_sha256"),
    "transfer_requests": ("proof", "proof_key", "proof_size", "proof_sha256"),
}


def upgrade() -> None:
    for table, (binary, key, size, sha) in TABLES.items():
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column(key, sa.String(300), nullable=True))
            batch.add_column(sa.Column(size, sa.Integer(), nullable=True))
            batch.add_column(sa.Column(sha, sa.String(64), nullable=True))
            if table != "transfer_requests":  # already optional
                batch.alter_column(binary, existing_type=sa.LargeBinary(), nullable=True)


def downgrade() -> None:
    connection = op.get_bind()
    for table, (binary, key, _size, _sha) in TABLES.items():
        moved = connection.execute(
            sa.text(f"SELECT COUNT(*) FROM {table} WHERE {key} IS NOT NULL AND {binary} IS NULL")
        ).scalar()
        if moved:
            raise RuntimeError(
                f"{table} tiene archivos solo en el almacenamiento; no se puede volver atrás"
            )
    for table, (binary, key, size, sha) in TABLES.items():
        with op.batch_alter_table(table) as batch:
            if table != "transfer_requests":
                batch.alter_column(binary, existing_type=sa.LargeBinary(), nullable=False)
            batch.drop_column(sha)
            batch.drop_column(size)
            batch.drop_column(key)
