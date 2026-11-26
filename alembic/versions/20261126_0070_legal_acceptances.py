"""Acceptances of the legal documents (Fase 5, step G3).

Global table: who accepted which version of the terms, the privacy policy or
the data processing agreement, for which institution and when.

Revision ID: 20261126_0070
Revises: 20261126_0069
"""

import sqlalchemy as sa

from alembic import op

revision = "20261126_0070"
down_revision = "20261126_0069"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "legal_acceptances",
        sa.Column("legal_acceptance_id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column(
            "institution_id",
            sa.Integer(),
            sa.ForeignKey("institutions.institution_id", name="fk_legal_acceptances_institution"),
            nullable=True,
        ),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=True),
        sa.Column("accepted_by", sa.String(255), nullable=False),
        sa.Column("ip", sa.String(64), nullable=False),
        sa.Column("accepted_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_legal_acceptances_kind", "legal_acceptances", ["kind"])
    op.create_index("ix_legal_acceptances_institution_id", "legal_acceptances", ["institution_id"])


def downgrade() -> None:
    op.drop_index("ix_legal_acceptances_institution_id", table_name="legal_acceptances")
    op.drop_index("ix_legal_acceptances_kind", table_name="legal_acceptances")
    op.drop_table("legal_acceptances")
