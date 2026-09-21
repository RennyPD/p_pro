"""Add course equivalences and career history.

Revision ID: 20260921_0017
Revises: 20260921_0016
"""
import sqlalchemy as sa
from alembic import op

revision = "20260921_0017"
down_revision = "20260921_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("course_equivalences", sa.Column("course_equivalence_id", sa.Integer(), primary_key=True), sa.Column("career_id", sa.Integer(), sa.ForeignKey("careers.career_id"), nullable=False), sa.Column("source_subject_id", sa.Integer(), sa.ForeignKey("subjects.subject_id"), nullable=False), sa.Column("target_subject_id", sa.Integer(), sa.ForeignKey("subjects.subject_id"), nullable=False), sa.Column("curriculum_version", sa.String(30), nullable=False, server_default="current"), sa.Column("notes", sa.Text(), nullable=False, server_default=""), sa.UniqueConstraint("career_id", "source_subject_id", "target_subject_id", name="uq_course_equivalence"))
    op.create_table("student_career_history", sa.Column("student_career_history_id", sa.Integer(), primary_key=True), sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.student_id"), nullable=False), sa.Column("previous_career_id", sa.Integer(), sa.ForeignKey("careers.career_id"), nullable=False), sa.Column("new_career_id", sa.Integer(), sa.ForeignKey("careers.career_id"), nullable=False), sa.Column("effective_date", sa.Date(), nullable=False), sa.Column("reason", sa.Text(), nullable=False), sa.Column("changed_by", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False))


def downgrade() -> None:
    op.drop_table("student_career_history")
    op.drop_table("course_equivalences")
