"""Add enrollment lifecycle, capacity and academic holds."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260918_0009"
down_revision: Union[str, None] = "20260918_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "academic_periods",
        sa.Column("status", sa.String(20), nullable=False, server_default="planning"),
    )
    for name in (
        "registration_start",
        "registration_end",
        "withdrawal_deadline",
        "grading_deadline",
    ):
        op.add_column("academic_periods", sa.Column(name, sa.Date(), nullable=True))
    op.add_column(
        "institution_settings",
        sa.Column("max_credits_per_period", sa.Integer(), nullable=False, server_default="24"),
    )
    op.add_column(
        "sections", sa.Column("capacity", sa.Integer(), nullable=False, server_default="30")
    )
    op.add_column(
        "sections", sa.Column("room", sa.String(100), nullable=False, server_default="Por asignar")
    )
    op.add_column(
        "sections",
        sa.Column("modality", sa.String(20), nullable=False, server_default="in_person"),
    )
    op.add_column(
        "students", sa.Column("academic_hold", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column(
        "students", sa.Column("financial_hold", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column("enrollments", sa.Column("waitlist_position", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("enrollments", "waitlist_position")
    op.drop_column("students", "financial_hold")
    op.drop_column("students", "academic_hold")
    op.drop_column("sections", "modality")
    op.drop_column("sections", "room")
    op.drop_column("sections", "capacity")
    op.drop_column("institution_settings", "max_credits_per_period")
    for name in (
        "grading_deadline",
        "withdrawal_deadline",
        "registration_end",
        "registration_start",
    ):
        op.drop_column("academic_periods", name)
    op.drop_column("academic_periods", "status")
