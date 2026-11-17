"""Add editable labels without changing persisted role codes."""

import sqlalchemy as sa

from alembic import op

revision = "20261117_0034"
down_revision = "20261117_0033"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("roles", sa.Column("label", sa.String(100)))


def downgrade():
    with op.batch_alter_table("roles") as batch:
        batch.drop_column("label")
