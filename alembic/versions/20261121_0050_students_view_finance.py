"""Institution setting: whether students see their own finances (decision 2).

Configurable per institution (product decision of 21/11/2026): usually hidden
in schools and shown in universities. Existing installations keep today's
behaviour (shown) until an administrator changes it.

Revision ID: 20261121_0050
Revises: 20261121_0049
"""

import sqlalchemy as sa

from alembic import op

revision = "20261121_0050"
down_revision = "20261121_0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("institution_settings") as batch:
        batch.add_column(
            sa.Column(
                "students_view_finance", sa.Boolean(), nullable=False, server_default=sa.true()
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("institution_settings") as batch:
        batch.drop_column("students_view_finance")
