"""Separate pending MFA enrollment and version account sessions."""

import sqlalchemy as sa

from alembic import op

revision = "20261117_0033"
down_revision = "20261014_0032"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("mfa_pending_secret", sa.String(64)))
    op.add_column("users", sa.Column("mfa_pending_until", sa.DateTime()))
    op.add_column("users", sa.Column("mfa_attempts", sa.Integer(), server_default="0", nullable=False))
    op.add_column("users", sa.Column("mfa_attempt_window", sa.DateTime()))
    op.add_column(
        "users", sa.Column("session_version", sa.Integer(), server_default="0", nullable=False)
    )


def downgrade():
    with op.batch_alter_table("users") as batch:
        batch.drop_column("session_version")
        batch.drop_column("mfa_attempt_window")
        batch.drop_column("mfa_attempts")
        batch.drop_column("mfa_pending_until")
        batch.drop_column("mfa_pending_secret")
