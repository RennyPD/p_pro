"""Per-link permissions between guardians and students (audit A1).

A guardian sees attendance, grades, balance, tasks and performance of every
linked student by default (product decision of 21/11/2026). Each link can now
restrict an area for a single guardian, and marks who is financially
responsible. Existing links keep seeing everything.

Revision ID: 20261121_0049
Revises: 20261121_0048
"""

import sqlalchemy as sa

from alembic import op

revision = "20261121_0049"
down_revision = "20261121_0048"
branch_labels = None
depends_on = None

VIEW_COLUMNS = ("can_view_academic", "can_view_attendance", "can_view_finance", "can_view_tasks")


def upgrade() -> None:
    with op.batch_alter_table("student_guardians") as batch:
        for column in VIEW_COLUMNS:
            batch.add_column(
                sa.Column(column, sa.Boolean(), nullable=False, server_default=sa.true())
            )
        batch.add_column(
            sa.Column(
                "financial_responsible", sa.Boolean(), nullable=False, server_default=sa.false()
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("student_guardians") as batch:
        batch.drop_column("financial_responsible")
        for column in reversed(VIEW_COLUMNS):
            batch.drop_column(column)
