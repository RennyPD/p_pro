"""Single-use TOTP steps and refresh token rotation marks (audit, low findings)."""

import sqlalchemy as sa

from alembic import op

revision = "20261118_0043"
down_revision = "20261118_0042"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("mfa_last_step", sa.Integer(), nullable=True))
    op.add_column("refresh_tokens", sa.Column("rotated_at", sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table("refresh_tokens") as batch:
        batch.drop_column("rotated_at")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("mfa_last_step")
