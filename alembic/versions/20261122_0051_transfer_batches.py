"""One bank transfer for several linked students (payments module, step 3).

A guardian reports a single transfer and splits it among their children.
The batch holds the bank reference and the proof; each student's share is a
regular transfer request linked to it, so its proof column becomes optional.

Revision ID: 20261122_0051
Revises: 20261121_0050
"""

import sqlalchemy as sa

from alembic import op

revision = "20261122_0051"
down_revision = "20261121_0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "transfer_batches",
        sa.Column("transfer_batch_id", sa.Integer(), primary_key=True),
        sa.Column("reference", sa.String(100), nullable=False, unique=True),
        sa.Column("bank", sa.String(100), nullable=False),
        sa.Column("note", sa.String(250), nullable=False),
        sa.Column("total_cents", sa.Integer(), nullable=False),
        sa.Column("proof", sa.LargeBinary(), nullable=False),
        sa.Column("proof_type", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("submitted_by", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("review_reason", sa.String(250), nullable=True),
    )
    with op.batch_alter_table("transfer_requests") as batch:
        batch.alter_column("proof", existing_type=sa.LargeBinary(), nullable=True)
        batch.add_column(sa.Column("batch_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_transfer_requests_batch", "transfer_batches", ["batch_id"], ["transfer_batch_id"]
        )
        batch.create_index("ix_transfer_requests_batch_id", ["batch_id"])


def downgrade() -> None:
    with op.batch_alter_table("transfer_requests") as batch:
        batch.drop_index("ix_transfer_requests_batch_id")
        batch.drop_constraint("fk_transfer_requests_batch", type_="foreignkey")
        batch.drop_column("batch_id")
        batch.alter_column("proof", existing_type=sa.LargeBinary(), nullable=False)
    op.drop_table("transfer_batches")
