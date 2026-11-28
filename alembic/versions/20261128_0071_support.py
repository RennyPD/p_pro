"""Support tickets (Fase 5, step G6). Global tables pointing to the institution.

Revision ID: 20261128_0071
Revises: 20261126_0070
"""

import sqlalchemy as sa

from alembic import op

revision = "20261128_0071"
down_revision = "20261126_0070"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "support_tickets",
        sa.Column("support_ticket_id", sa.Integer(), primary_key=True),
        sa.Column(
            "institution_id",
            sa.Integer(),
            sa.ForeignKey("institutions.institution_id", name="fk_support_tickets_institution"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=True),
        sa.Column("requester_name", sa.String(150), nullable=False),
        sa.Column("requester_email", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(150), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("priority", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_support_tickets_institution_id", "support_tickets", ["institution_id"])
    op.create_index("ix_support_tickets_status", "support_tickets", ["status"])
    op.create_table(
        "support_messages",
        sa.Column("support_message_id", sa.Integer(), primary_key=True),
        sa.Column(
            "support_ticket_id",
            sa.Integer(),
            sa.ForeignKey("support_tickets.support_ticket_id"),
            nullable=False,
        ),
        sa.Column("author_kind", sa.String(12), nullable=False),
        sa.Column("author_user_id", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=True),
        sa.Column(
            "author_platform_admin_id",
            sa.Integer(),
            sa.ForeignKey("platform_admins.platform_admin_id"),
            nullable=True,
        ),
        sa.Column("author_name", sa.String(150), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_support_messages_support_ticket_id", "support_messages", ["support_ticket_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_support_messages_support_ticket_id", table_name="support_messages")
    op.drop_table("support_messages")
    op.drop_index("ix_support_tickets_status", table_name="support_tickets")
    op.drop_index("ix_support_tickets_institution_id", table_name="support_tickets")
    op.drop_table("support_tickets")
