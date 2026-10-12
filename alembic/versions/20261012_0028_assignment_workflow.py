"""Assignment policies and immutable submission attempts."""

import sqlalchemy as sa

from alembic import op

revision = "20261012_0028"
down_revision = "20261012_0027"
branch_labels = None
depends_on = None


def upgrade():
    duplicates = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT assessment_id FROM assignments WHERE assessment_id IS NOT NULL GROUP BY assessment_id HAVING COUNT(*) > 1"
            )
        )
        .first()
    )
    if duplicates:
        raise RuntimeError(
            "Hay varias tareas para una misma evaluación. Revisar la política de agregación antes de migrar; no se eliminan datos."
        )
    op.create_index(
        "uq_assignment_assessment",
        "assignments",
        ["assessment_id"],
        unique=True,
        sqlite_where=sa.text("assessment_id IS NOT NULL"),
        postgresql_where=sa.text("assessment_id IS NOT NULL"),
    )
    op.add_column(
        "assignments", sa.Column("lifecycle", sa.String(20), nullable=False, server_default="open")
    )
    op.add_column(
        "assignments",
        sa.Column("allow_late", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "assignments",
        sa.Column("allow_resubmit", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "submission_revisions",
        sa.Column("revision_id", sa.Integer(), primary_key=True),
        sa.Column(
            "submission_id",
            sa.Integer(),
            sa.ForeignKey("submissions.submission_id"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
    )
    op.execute(
        sa.text(
            "INSERT INTO submission_revisions (submission_id, content, submitted_at) SELECT submission_id, content, submitted_at FROM submissions"
        )
    )


def downgrade():
    op.drop_table("submission_revisions")
    with op.batch_alter_table("assignments") as batch:
        for name in ("lifecycle", "allow_late", "allow_resubmit"):
            batch.drop_column(name)
    op.drop_index("uq_assignment_assessment", table_name="assignments")
