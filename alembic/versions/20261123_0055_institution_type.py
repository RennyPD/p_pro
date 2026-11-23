"""Institution type: university, school or both (Fase 3, block A2).

Existing installations keep working as universities. School levels are
academic levels of a program (initial, primary, secondary; no new column).

Revision ID: 20261123_0055
Revises: 20261123_0054
"""

import sqlalchemy as sa

from alembic import op

revision = "20261123_0055"
down_revision = "20261123_0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("institution_settings") as batch:
        batch.add_column(
            sa.Column(
                "institution_type", sa.String(20), nullable=False, server_default="university"
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("institution_settings") as batch:
        batch.drop_column("institution_type")
