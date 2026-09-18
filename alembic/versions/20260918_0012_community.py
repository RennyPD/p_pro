"""Add guardians, announcements and internal notifications."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260918_0012"
down_revision: Union[str, None] = "20260918_0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "guardians",
        sa.Column("guardian_id", sa.Integer(), primary_key=True),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("telephone", sa.String(30), nullable=False),
        sa.Column("address", sa.String(255), nullable=False),
    )
    op.create_table(
        "student_guardians",
        sa.Column("student_guardian_id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.student_id"), nullable=False),
        sa.Column("guardian_id", sa.Integer(), sa.ForeignKey("guardians.guardian_id"), nullable=False),
        sa.Column("relationship", sa.String(50), nullable=False),
        sa.Column("primary_contact", sa.Boolean(), nullable=False),
        sa.Column("emergency_contact", sa.Boolean(), nullable=False),
        sa.Column("authorized_pickup", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("student_id", "guardian_id", name="uq_student_guardian"),
    )
    op.create_table(
        "announcements",
        sa.Column("announcement_id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(150), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("audience", sa.String(20), nullable=False),
        sa.Column("section_id", sa.Integer(), sa.ForeignKey("sections.section_id"), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "notifications",
        sa.Column("notification_id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("title", sa.String(150), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("read_at", sa.DateTime(), nullable=True),
    )
    op.create_index("idx_notifications_user", "notifications", ["user_id"])


def downgrade() -> None:
    op.drop_index("idx_notifications_user", table_name="notifications")
    op.drop_table("notifications")
    op.drop_table("announcements")
    op.drop_table("student_guardians")
    op.drop_table("guardians")
