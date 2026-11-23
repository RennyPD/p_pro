"""Grading scales per program and recovery exams (Fase 3, block D).

Creates the default scale "Numérica 0–100" with the institution's current
passing grade, so nothing changes until someone configures another scale.
Grades keep their 0–100 values.

Revision ID: 20261123_0058
Revises: 20261123_0057
"""

import sqlalchemy as sa

from alembic import op

revision = "20261123_0058"
down_revision = "20261123_0057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "grading_scales",
        sa.Column("grading_scale_id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("passing_value", sa.Numeric(5, 2), nullable=False),
        sa.Column("decimals", sa.Integer(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("completivo_average_weight", sa.Numeric(5, 2), nullable=False),
        sa.Column("extraordinario_average_weight", sa.Numeric(5, 2), nullable=False),
        sa.UniqueConstraint("name", name="uq_grading_scales_name"),
    )
    op.create_table(
        "grading_scale_bands",
        sa.Column("band_id", sa.Integer(), primary_key=True),
        sa.Column(
            "grading_scale_id",
            sa.Integer(),
            sa.ForeignKey("grading_scales.grading_scale_id"),
            nullable=False,
        ),
        sa.Column("label", sa.String(40), nullable=False),
        sa.Column("description", sa.String(120), nullable=True),
        sa.Column("min_value", sa.Numeric(5, 2), nullable=False),
        sa.Column("max_value", sa.Numeric(5, 2), nullable=False),
        sa.Column("stored_value", sa.Numeric(5, 2), nullable=False),
        sa.Column("points", sa.Numeric(4, 2), nullable=True),
    )
    op.create_index(
        "ix_grading_scale_bands_grading_scale_id", "grading_scale_bands", ["grading_scale_id"]
    )
    op.create_table(
        "recovery_exams",
        sa.Column("recovery_exam_id", sa.Integer(), primary_key=True),
        sa.Column(
            "member_id",
            sa.Integer(),
            sa.ForeignKey("class_group_members.member_id"),
            nullable=False,
        ),
        sa.Column("subject_id", sa.Integer(), sa.ForeignKey("subjects.subject_id"), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("annual_average", sa.Numeric(5, 2), nullable=False),
        sa.Column("exam_grade", sa.Numeric(5, 2), nullable=False),
        sa.Column("final_grade", sa.Numeric(5, 2), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("recorded_by", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=True),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("member_id", "subject_id", "kind", name="uq_recovery_exam"),
    )
    op.create_index("ix_recovery_exams_member_id", "recovery_exams", ["member_id"])
    with op.batch_alter_table("careers") as batch:
        batch.add_column(sa.Column("grading_scale_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_careers_grading_scale", "grading_scales", ["grading_scale_id"], ["grading_scale_id"]
        )
        batch.create_index("ix_careers_grading_scale_id", ["grading_scale_id"])
    connection = op.get_bind()
    passing = connection.execute(
        sa.text("SELECT passing_grade FROM institution_settings ORDER BY settings_id LIMIT 1")
    ).scalar()
    connection.execute(
        sa.text(
            "INSERT INTO grading_scales (name, kind, passing_value, decimals, is_default, "
            "completivo_average_weight, extraordinario_average_weight) VALUES "
            "('Numérica 0–100', 'numeric', :passing, 0, TRUE, 50, 30)"
        ),
        {"passing": passing if passing is not None else 70},
    )


def downgrade() -> None:
    with op.batch_alter_table("careers") as batch:
        batch.drop_index("ix_careers_grading_scale_id")
        batch.drop_constraint("fk_careers_grading_scale", type_="foreignkey")
        batch.drop_column("grading_scale_id")
    op.drop_table("recovery_exams")
    op.drop_table("grading_scale_bands")
    op.drop_table("grading_scales")
