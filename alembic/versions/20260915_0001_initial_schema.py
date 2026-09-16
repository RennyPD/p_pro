"""Initial educational management schema."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260915_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "careers",
        sa.Column("career_id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.String(255), nullable=False),
    )
    op.create_table(
        "roles",
        sa.Column("role_id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(50), nullable=False, unique=True),
        sa.Column("description", sa.String(255), nullable=False),
    )
    op.create_table(
        "subjects",
        sa.Column("subject_id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.String(255), nullable=False),
    )
    op.create_table(
        "teachers",
        sa.Column("teacher_id", sa.Integer(), primary_key=True),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("specialty", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("telephone", sa.String(20), nullable=False),
        sa.Column("address", sa.String(255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "students",
        sa.Column("student_id", sa.Integer(), primary_key=True),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("enrollment_number", sa.String(50), nullable=False, unique=True),
        sa.Column("telephone", sa.String(20), nullable=False),
        sa.Column("address", sa.String(255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("career_id", sa.Integer(), sa.ForeignKey("careers.career_id"), nullable=False),
    )
    op.create_table(
        "sections",
        sa.Column("section_id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("teacher_id", sa.Integer(), sa.ForeignKey("teachers.teacher_id"), nullable=False),
        sa.Column("subject_id", sa.Integer(), sa.ForeignKey("subjects.subject_id"), nullable=False),
        sa.Column("days_of_week", sa.String(255), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
    )
    op.create_table(
        "users",
        sa.Column("user_id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(50), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password", sa.String(255), nullable=False),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.role_id"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.student_id"), nullable=True),
        sa.Column("teacher_id", sa.Integer(), sa.ForeignKey("teachers.teacher_id"), nullable=True),
    )
    op.create_table(
        "enrollments",
        sa.Column("enrollment_id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.student_id"), nullable=False),
        sa.Column("section_id", sa.Integer(), sa.ForeignKey("sections.section_id"), nullable=False),
        sa.Column("enrollment_date", sa.DateTime(), nullable=False),
        sa.Column("state", sa.String(50), nullable=False),
        sa.Column("period", sa.String(50), nullable=False),
    )
    op.create_table(
        "attendances",
        sa.Column("attendance_id", sa.Integer(), primary_key=True),
        sa.Column("enrollment_id", sa.Integer(), sa.ForeignKey("enrollments.enrollment_id"), nullable=False),
        sa.Column("date", sa.DateTime(), nullable=False),
        sa.Column("present", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "grades",
        sa.Column("grade_id", sa.Integer(), primary_key=True),
        sa.Column("enrollment_id", sa.Integer(), sa.ForeignKey("enrollments.enrollment_id"), nullable=False),
        sa.Column("grade_value", sa.Float(), nullable=False),
        sa.Column("grade_type", sa.String(50), nullable=False),
        sa.Column("date_recorded", sa.String(50), nullable=False),
    )


def downgrade() -> None:
    for table in (
        "grades", "attendances", "enrollments", "users", "sections",
        "students", "teachers", "subjects", "roles", "careers",
    ):
        op.drop_table(table)
