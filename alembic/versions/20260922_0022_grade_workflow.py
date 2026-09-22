"""Add grade draft workflow and history.

Revision ID: 20260922_0022
Revises: 20260922_0021
"""

import sqlalchemy as sa

from alembic import op

revision = "20260922_0022"
down_revision = "20260922_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("grades") as batch:
        batch.add_column(
            sa.Column("status", sa.String(20), nullable=False, server_default="published")
        )
        batch.add_column(sa.Column("updated_by", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("updated_at", sa.DateTime(), nullable=True))
        batch.create_foreign_key("fk_grades_updated_by_users", "users", ["updated_by"], ["user_id"])
    op.create_table(
        "grade_changes",
        sa.Column("grade_change_id", sa.Integer(), primary_key=True),
        sa.Column("grade_id", sa.Integer(), sa.ForeignKey("grades.grade_id"), nullable=False),
        sa.Column("previous_value", sa.Float(), nullable=True),
        sa.Column("new_value", sa.Float(), nullable=False),
        sa.Column("changed_by", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("reason", sa.String(250), nullable=False),
        sa.Column("changed_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("grade_changes")
    with op.batch_alter_table("grades") as batch:
        batch.drop_constraint("fk_grades_updated_by_users", type_="foreignkey")
        batch.drop_column("updated_at")
        batch.drop_column("updated_by")
        batch.drop_column("status")
