"""Store sign-in throttling counters in the database (audit M4)."""

import sqlalchemy as sa

from alembic import op

revision = "20261118_0040"
down_revision = "20261118_0039"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "login_throttles",
        sa.Column("login_throttle_id", sa.Integer(), primary_key=True),
        sa.Column("throttle_key", sa.String(320), nullable=False),
        sa.Column("failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("window_started_at", sa.DateTime(), nullable=False),
        sa.Column("blocked_until", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_login_throttles_throttle_key", "login_throttles", ["throttle_key"], unique=True
    )


def downgrade():
    op.drop_index("ix_login_throttles_throttle_key", table_name="login_throttles")
    op.drop_table("login_throttles")
