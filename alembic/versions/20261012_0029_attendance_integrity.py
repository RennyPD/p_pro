"""Daily attendance identity and durable corrections history."""

import sqlalchemy as sa

from alembic import op

revision = "20261012_0029"
down_revision = "20261012_0028"
branch_labels = None
depends_on = None


def upgrade():
    duplicate = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT enrollment_id, date(date) FROM attendances GROUP BY enrollment_id, date(date) HAVING COUNT(*) > 1"
            )
        )
        .first()
    )
    if duplicate:
        raise RuntimeError(
            "Hay asistencias duplicadas por estudiante y día. Revisar antes de migrar; no se elimina ningún registro."
        )
    op.create_index(
        "uq_attendance_enrollment_day",
        "attendances",
        ["enrollment_id", sa.text("date(date)")],
        unique=True,
    )
    op.create_table(
        "attendance_changes",
        sa.Column("change_id", sa.Integer(), primary_key=True),
        sa.Column("attendance_id", sa.Integer(), nullable=False),
        sa.Column("enrollment_id", sa.Integer(), nullable=False),
        sa.Column("changed_by", sa.Integer(), nullable=False),
        sa.Column("changed_by_name", sa.String(100), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("reason", sa.String(250), nullable=False),
        sa.Column("previous", sa.JSON(), nullable=True),
        sa.Column("current", sa.JSON(), nullable=True),
        sa.Column("changed_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_attendance_changes_attendance_id", "attendance_changes", ["attendance_id"])
    op.create_index("ix_attendance_changes_enrollment_id", "attendance_changes", ["enrollment_id"])


def downgrade():
    op.drop_table("attendance_changes")
    op.drop_index("uq_attendance_enrollment_day", table_name="attendances")
