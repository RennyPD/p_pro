"""Add classrooms, section meetings and advanced attendance."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260918_0010"
down_revision: Union[str, None] = "20260918_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "classrooms",
        sa.Column("classroom_id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("location", sa.String(200), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "section_meetings",
        sa.Column("meeting_id", sa.Integer(), primary_key=True),
        sa.Column("section_id", sa.Integer(), sa.ForeignKey("sections.section_id"), nullable=False),
        sa.Column("classroom_id", sa.Integer(), sa.ForeignKey("classrooms.classroom_id"), nullable=True),
        sa.Column("day_of_week", sa.String(20), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("modality", sa.String(20), nullable=False),
        sa.Column("virtual_url", sa.String(500), nullable=False),
        sa.UniqueConstraint("section_id", "day_of_week", "start_time", name="uq_section_meeting_slot"),
    )
    op.add_column("attendances", sa.Column("status", sa.String(20), nullable=False, server_default="absent"))
    op.add_column("attendances", sa.Column("note", sa.String(300), nullable=False, server_default=""))
    op.add_column("attendances", sa.Column("excuse_reference", sa.String(300), nullable=False, server_default=""))
    op.execute("UPDATE attendances SET status = CASE WHEN present THEN 'present' ELSE 'absent' END")


def downgrade() -> None:
    op.drop_column("attendances", "excuse_reference")
    op.drop_column("attendances", "note")
    op.drop_column("attendances", "status")
    op.drop_table("section_meetings")
    op.drop_table("classrooms")
