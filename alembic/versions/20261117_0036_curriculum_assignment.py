"""Allow parallel curricula and preserve credits for new enrollments."""

import sqlalchemy as sa

from alembic import op

revision = "20261117_0036"
down_revision = "20261117_0035"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("students", sa.Column("assigned_curriculum_version", sa.String(30)))
    op.add_column("enrollments", sa.Column("curriculum_version", sa.String(30)))
    op.add_column("enrollments", sa.Column("curriculum_credits", sa.Float()))
    with op.batch_alter_table("curriculum_courses") as batch:
        batch.drop_constraint("uq_curriculum_career_subject", type_="unique")
        batch.create_unique_constraint(
            "uq_curriculum_version_subject", ["career_id", "subject_id", "curriculum_version"]
        )


def downgrade():
    with op.batch_alter_table("curriculum_courses") as batch:
        batch.drop_constraint("uq_curriculum_version_subject", type_="unique")
        batch.create_unique_constraint("uq_curriculum_career_subject", ["career_id", "subject_id"])
    for table, columns in (
        ("enrollments", ("curriculum_version", "curriculum_credits")),
        ("students", ("assigned_curriculum_version",)),
    ):
        with op.batch_alter_table(table) as batch:
            for column in columns:
                batch.drop_column(column)
