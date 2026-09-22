"""Add persistent course selection cart.

Revision ID: 20260922_0021
Revises: 20260921_0020
"""

import sqlalchemy as sa

from alembic import op

revision = "20260922_0021"
down_revision = "20260921_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "course_selection_cart",
        sa.Column("cart_item_id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.student_id"), nullable=False),
        sa.Column("section_id", sa.Integer(), sa.ForeignKey("sections.section_id"), nullable=False),
        sa.Column("period", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "student_id", "section_id", "period", name="uq_cart_student_section_period"
        ),
    )


def downgrade() -> None:
    op.drop_table("course_selection_cart")
