"""Add an active flag to user accounts so they can be deactivated instead of deleted."""

import sqlalchemy as sa

from alembic import op

revision = "20261117_0038"
down_revision = "20261117_0037"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade():
    with op.batch_alter_table("users") as batch:
        batch.drop_column("active")
