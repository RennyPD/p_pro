"""Add per-account read-only module grants."""

import sqlalchemy as sa

from alembic import op

revision = "20261117_0037"
down_revision = "20261117_0036"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("module_views", sa.JSON()))


def downgrade():
    with op.batch_alter_table("users") as batch:
        batch.drop_column("module_views")
