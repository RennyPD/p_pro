"""Fixed class groups, their subject teachers and members (Fase 3, block C).

New, optional tables: existing data is not touched. Sections get a nullable
class_group_id for the subjects generated for a group.

Revision ID: 20261123_0057
Revises: 20261123_0056
"""

import sqlalchemy as sa

from alembic import op

revision = "20261123_0057"
down_revision = "20261123_0056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "class_groups",
        sa.Column("class_group_id", sa.Integer(), primary_key=True),
        sa.Column("career_id", sa.Integer(), sa.ForeignKey("careers.career_id"), nullable=False),
        sa.Column("grade_number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(20), nullable=False),
        sa.Column(
            "school_year_id",
            sa.Integer(),
            sa.ForeignKey("school_years.school_year_id"),
            nullable=False,
        ),
        sa.Column(
            "homeroom_teacher_id",
            sa.Integer(),
            sa.ForeignKey("teachers.teacher_id"),
            nullable=True,
        ),
        sa.Column("room", sa.String(100), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.UniqueConstraint(
            "career_id", "grade_number", "name", "school_year_id", name="uq_class_group_identity"
        ),
    )
    op.create_index("ix_class_groups_career_id", "class_groups", ["career_id"])
    op.create_index("ix_class_groups_school_year_id", "class_groups", ["school_year_id"])
    op.create_index("ix_class_groups_homeroom_teacher_id", "class_groups", ["homeroom_teacher_id"])
    op.create_table(
        "class_group_subjects",
        sa.Column("class_group_subject_id", sa.Integer(), primary_key=True),
        sa.Column(
            "class_group_id",
            sa.Integer(),
            sa.ForeignKey("class_groups.class_group_id"),
            nullable=False,
        ),
        sa.Column("subject_id", sa.Integer(), sa.ForeignKey("subjects.subject_id"), nullable=False),
        sa.Column("teacher_id", sa.Integer(), sa.ForeignKey("teachers.teacher_id"), nullable=False),
        sa.UniqueConstraint("class_group_id", "subject_id", name="uq_class_group_subject"),
    )
    op.create_index(
        "ix_class_group_subjects_class_group_id", "class_group_subjects", ["class_group_id"]
    )
    op.create_table(
        "class_group_members",
        sa.Column("member_id", sa.Integer(), primary_key=True),
        sa.Column(
            "class_group_id",
            sa.Integer(),
            sa.ForeignKey("class_groups.class_group_id"),
            nullable=False,
        ),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.student_id"), nullable=False),
        sa.Column(
            "school_year_id",
            sa.Integer(),
            sa.ForeignKey("school_years.school_year_id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("joined_on", sa.Date(), nullable=False),
        sa.Column("left_on", sa.Date(), nullable=True),
        sa.Column("result", sa.String(20), nullable=False),
        sa.Column("result_confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("result_note", sa.Text(), nullable=True),
        sa.UniqueConstraint("student_id", "school_year_id", name="uq_class_group_member_year"),
    )
    op.create_index(
        "ix_class_group_members_class_group_id", "class_group_members", ["class_group_id"]
    )
    op.create_index("ix_class_group_members_student_id", "class_group_members", ["student_id"])
    with op.batch_alter_table("sections") as batch:
        batch.add_column(sa.Column("class_group_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_sections_class_group", "class_groups", ["class_group_id"], ["class_group_id"]
        )
        batch.create_index("ix_sections_class_group_id", ["class_group_id"])


def downgrade() -> None:
    with op.batch_alter_table("sections") as batch:
        batch.drop_index("ix_sections_class_group_id")
        batch.drop_constraint("fk_sections_class_group", type_="foreignkey")
        batch.drop_column("class_group_id")
    op.drop_table("class_group_members")
    op.drop_table("class_group_subjects")
    op.drop_table("class_groups")
