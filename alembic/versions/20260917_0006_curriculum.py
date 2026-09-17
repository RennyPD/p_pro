"""Add curriculum courses and prerequisites."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260917_0006"
down_revision: Union[str, None] = "20260917_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "curriculum_courses",
        sa.Column("curriculum_course_id", sa.Integer(), primary_key=True),
        sa.Column("career_id", sa.Integer(), sa.ForeignKey("careers.career_id"), nullable=False),
        sa.Column("subject_id", sa.Integer(), sa.ForeignKey("subjects.subject_id"), nullable=False),
        sa.Column("term_number", sa.Integer(), nullable=False),
        sa.Column("credits", sa.Float(), nullable=False),
        sa.Column("prerequisite_subject_id", sa.Integer(), sa.ForeignKey("subjects.subject_id"), nullable=True),
        sa.UniqueConstraint("career_id", "subject_id", name="uq_curriculum_career_subject"),
    )
    op.create_index("idx_curriculum_career_term", "curriculum_courses", ["career_id", "term_number"])


def downgrade() -> None:
    op.drop_index("idx_curriculum_career_term", table_name="curriculum_courses")
    op.drop_table("curriculum_courses")
