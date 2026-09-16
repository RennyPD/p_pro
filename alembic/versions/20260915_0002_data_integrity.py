"""Add schedule, grade and enrollment integrity constraints."""

from typing import Sequence, Union

from alembic import op

revision: str = "20260915_0002"
down_revision: Union[str, None] = "20260915_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("grades") as batch_op:
        batch_op.create_check_constraint(
            "ck_grades_value_range", "grade_value >= 0 AND grade_value <= 100"
        )
    with op.batch_alter_table("sections") as batch_op:
        batch_op.create_check_constraint("ck_sections_time_range", "start_time < end_time")
    with op.batch_alter_table("enrollments") as batch_op:
        batch_op.create_unique_constraint(
            "uq_enrollment_student_section_period",
            ["student_id", "section_id", "period"],
        )


def downgrade() -> None:
    with op.batch_alter_table("enrollments") as batch_op:
        batch_op.drop_constraint("uq_enrollment_student_section_period", type_="unique")
    with op.batch_alter_table("sections") as batch_op:
        batch_op.drop_constraint("ck_sections_time_range", type_="check")
    with op.batch_alter_table("grades") as batch_op:
        batch_op.drop_constraint("ck_grades_value_range", type_="check")
