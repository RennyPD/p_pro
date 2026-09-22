"""Add reusable assessment templates.

Revision ID: 20260922_0023
Revises: 20260922_0022
"""

import sqlalchemy as sa

from alembic import op

revision = "20260922_0023"
down_revision = "20260922_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assessment_templates",
        sa.Column("assessment_template_id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.UniqueConstraint("owner_id", "name", name="uq_assessment_template_owner_name"),
    )


def downgrade() -> None:
    op.drop_table("assessment_templates")
