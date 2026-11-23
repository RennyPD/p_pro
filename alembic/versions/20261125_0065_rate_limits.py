"""Request limits on uploads, exports, imports and public routes (Fase 4 C, audit B7).

Global table (no institution column): keys name the institution and account,
or the client address.

Revision ID: 20261125_0065
Revises: 20261125_0064
"""

import sqlalchemy as sa

from alembic import op

revision = "20261125_0065"
down_revision = "20261125_0064"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rate_limits",
        sa.Column("rate_key", sa.String(200), primary_key=True),
        sa.Column("window_start", sa.DateTime(), nullable=False),
        sa.Column("hits", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_rate_limits_window_start", "rate_limits", ["window_start"])


def downgrade() -> None:
    op.drop_index("ix_rate_limits_window_start", table_name="rate_limits")
    op.drop_table("rate_limits")
