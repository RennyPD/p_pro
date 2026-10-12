"""Grading identity, audit states and subject evaluation plans."""

import sqlalchemy as sa
from alembic import op

revision = "20261012_0027"
down_revision = "20261010_0026"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    duplicates = connection.execute(sa.text("SELECT enrollment_id, assessment_id FROM grades WHERE assessment_id IS NOT NULL GROUP BY enrollment_id, assessment_id HAVING COUNT(*) > 1")).first()
    if duplicates:
        raise RuntimeError("Existen notas duplicadas. No se eliminarán automáticamente; revisar antes de migrar.")
    op.create_index("uq_grade_enrollment_assessment", "grades", ["enrollment_id", "assessment_id"], unique=True, sqlite_where=sa.text("assessment_id IS NOT NULL"), postgresql_where=sa.text("assessment_id IS NOT NULL"))
    op.add_column("grade_changes", sa.Column("action", sa.String(20), nullable=False, server_default="updated"))
    op.add_column("grade_changes", sa.Column("previous_status", sa.String(20), nullable=True))
    op.add_column("grade_changes", sa.Column("new_status", sa.String(20), nullable=True))
    with op.batch_alter_table("assessment_templates") as batch:
        batch.add_column(sa.Column("subject_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("components", sa.JSON(), nullable=True))
        batch.create_foreign_key("fk_template_subject", "subjects", ["subject_id"], ["subject_id"])


def downgrade():
    with op.batch_alter_table("assessment_templates") as batch:
        batch.drop_constraint("fk_template_subject", type_="foreignkey")
        batch.drop_column("components")
        batch.drop_column("subject_id")
    with op.batch_alter_table("grade_changes") as batch:
        for name in ("action", "previous_status", "new_status"):
            batch.drop_column(name)
    op.drop_index("uq_grade_enrollment_assessment", table_name="grades")
