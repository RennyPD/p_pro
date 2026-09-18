"""Add weighted assessments and grade closing."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260918_0008"
down_revision: Union[str, None] = "20260917_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "assessments",
        sa.Column("assessment_id", sa.Integer(), primary_key=True),
        sa.Column("section_id", sa.Integer(), sa.ForeignKey("sections.section_id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("closed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("section_id", "name", name="uq_assessment_section_name"),
    )
    op.add_column("grades", sa.Column("assessment_id", sa.Integer(), nullable=True))
    with op.batch_alter_table("grades") as batch:
        batch.create_foreign_key(
            "fk_grades_assessment_id", "assessments", ["assessment_id"], ["assessment_id"]
        )
    op.create_index("idx_assessments_section", "assessments", ["section_id"])


def downgrade() -> None:
    with op.batch_alter_table("grades") as batch:
        batch.drop_constraint("fk_grades_assessment_id", type_="foreignkey")
        batch.drop_column("assessment_id")
    op.drop_index("idx_assessments_section", table_name="assessments")
    op.drop_table("assessments")
