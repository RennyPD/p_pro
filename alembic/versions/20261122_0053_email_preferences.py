"""Email notice preferences per account (audit M6, step 3).

Every account receives announcements, published grades and due-date reminders
by email unless the person turns them off. Security emails cannot be disabled.

Revision ID: 20261122_0053
Revises: 20261122_0052
"""

import sqlalchemy as sa

from alembic import op

revision = "20261122_0053"
down_revision = "20261122_0052"
branch_labels = None
depends_on = None

COLUMNS = ("email_announcements", "email_grades", "email_due_reminders")


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        for column in COLUMNS:
            batch.add_column(
                sa.Column(column, sa.Boolean(), nullable=False, server_default=sa.true())
            )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        for column in reversed(COLUMNS):
            batch.drop_column(column)
