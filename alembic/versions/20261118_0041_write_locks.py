"""Keyed write locks replace the single governance and finance rows (audit M7)."""

import sqlalchemy as sa

from alembic import op

revision = "20261118_0041"
down_revision = "20261118_0040"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "write_locks",
        sa.Column("lock_key", sa.String(120), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.drop_table("governance_control")
    op.drop_table("finance_control")


def downgrade():
    op.create_table(
        "finance_control",
        sa.Column("finance_control_id", sa.Integer(), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=True),
    )
    op.create_table(
        "governance_control",
        sa.Column("governance_control_id", sa.Integer(), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=True),
    )
    op.drop_table("write_locks")
