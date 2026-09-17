"""Add academic periods and institution settings."""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260917_0005"
down_revision: Union[str, None] = "20260916_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "academic_periods",
        sa.Column("period_id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(50), nullable=False, unique=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "institution_settings",
        sa.Column("settings_id", sa.Integer(), primary_key=True),
        sa.Column("institution_name", sa.String(150), nullable=False),
        sa.Column("enrollment_prefix", sa.String(20), nullable=False),
        sa.Column("enrollment_digits", sa.Integer(), nullable=False),
        sa.Column("next_enrollment_number", sa.Integer(), nullable=False),
        sa.Column("passing_grade", sa.Float(), nullable=False),
    )
    op.execute(
        "INSERT INTO institution_settings "
        "(settings_id, institution_name, enrollment_prefix, enrollment_digits, next_enrollment_number, passing_grade) "
        "VALUES (1, 'Nexo Académico', 'EST', 4, 1, 70)"
    )


def downgrade() -> None:
    op.drop_table("institution_settings")
    op.drop_table("academic_periods")
