"""Platform super administration (Fase 4, block B).

Global tables (no institution, no RLS): platform_admins with a mandatory
second factor and platform_audit_logs. Institutions get a contact email and
the reason and date of their last status change.

Revision ID: 20261124_0063
Revises: 20261124_0062
"""

import sqlalchemy as sa

from alembic import op

revision = "20261124_0063"
down_revision = "20261124_0062"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_admins",
        sa.Column("platform_admin_id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("password", sa.String(255), nullable=False),
        sa.Column("mfa_secret", sa.String(64), nullable=False),
        sa.Column("mfa_last_step", sa.Integer(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("session_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("email", name="uq_platform_admins_email"),
    )
    op.create_table(
        "platform_audit_logs",
        sa.Column("platform_audit_log_id", sa.Integer(), primary_key=True),
        sa.Column(
            "platform_admin_id",
            sa.Integer(),
            sa.ForeignKey("platform_admins.platform_admin_id"),
            nullable=True,
        ),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("resource", sa.String(120), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    with op.batch_alter_table("institutions") as batch:
        batch.add_column(sa.Column("contact_email", sa.String(255), nullable=True))
        batch.add_column(sa.Column("status_reason", sa.String(250), nullable=True))
        batch.add_column(sa.Column("status_changed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("institutions") as batch:
        batch.drop_column("status_changed_at")
        batch.drop_column("status_reason")
        batch.drop_column("contact_email")
    op.drop_table("platform_audit_logs")
    op.drop_table("platform_admins")
