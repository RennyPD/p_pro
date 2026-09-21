"""Add academic governance metadata.

Revision ID: 20260921_0016
Revises: 20260918_0015
"""

import sqlalchemy as sa
from alembic import op

revision = "20260921_0016"
down_revision = "20260918_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("sections") as batch:
        batch.add_column(sa.Column("status", sa.String(20), nullable=False, server_default="published"))
        batch.add_column(sa.Column("minimum_capacity", sa.Integer(), nullable=False, server_default="1"))
        batch.add_column(sa.Column("period_name", sa.String(50), nullable=False, server_default=""))
    with op.batch_alter_table("curriculum_courses") as batch:
        batch.add_column(sa.Column("corequisite_subject_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("course_type", sa.String(20), nullable=False, server_default="required"))
        batch.add_column(sa.Column("curriculum_version", sa.String(30), nullable=False, server_default="current"))
        batch.create_foreign_key("fk_curriculum_corequisite", "subjects", ["corequisite_subject_id"], ["subject_id"])
    with op.batch_alter_table("careers") as batch:
        batch.add_column(sa.Column("required_credits", sa.Integer(), nullable=False, server_default="120"))
        batch.add_column(sa.Column("curriculum_version", sa.String(30), nullable=False, server_default="current"))
    op.execute("UPDATE sections SET period_name = (SELECT name FROM academic_periods WHERE active = 1 LIMIT 1) WHERE period_name = ''")


def downgrade() -> None:
    with op.batch_alter_table("careers") as batch:
        batch.drop_column("curriculum_version")
        batch.drop_column("required_credits")
    with op.batch_alter_table("curriculum_courses") as batch:
        batch.drop_constraint("fk_curriculum_corequisite", type_="foreignkey")
        batch.drop_column("curriculum_version")
        batch.drop_column("course_type")
        batch.drop_column("corequisite_subject_id")
    with op.batch_alter_table("sections") as batch:
        batch.drop_column("period_name")
        batch.drop_column("minimum_capacity")
        batch.drop_column("status")
