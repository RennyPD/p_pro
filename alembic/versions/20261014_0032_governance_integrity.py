"""Notification provenance, stable passing thresholds and reversible period closures."""

import sqlalchemy as sa

from alembic import op

revision = "20261014_0032"
down_revision = "20261012_0031"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("admission_applications") as batch:
        batch.add_column(sa.Column("student_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_admission_student", "students", ["student_id"], ["student_id"])
    with op.batch_alter_table("institution_settings") as batch:
        batch.add_column(sa.Column("revision", sa.Integer(), nullable=False, server_default="0"))
    with op.batch_alter_table("announcements") as batch:
        batch.add_column(sa.Column("delivery_key", sa.String(100), nullable=True))
        batch.create_unique_constraint("uq_announcement_delivery_key", ["delivery_key"])
    with op.batch_alter_table("notifications") as batch:
        batch.add_column(sa.Column("announcement_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_notification_announcement",
            "announcements",
            ["announcement_id"],
            ["announcement_id"],
        )
        batch.create_index("ix_notifications_announcement_id", ["announcement_id"])
    with op.batch_alter_table("academic_periods") as batch:
        batch.add_column(sa.Column("closure_snapshot", sa.Text(), nullable=True))
    with op.batch_alter_table("enrollments") as batch:
        batch.add_column(sa.Column("passing_grade", sa.Float(), nullable=True))
    op.execute(
        sa.text(
            "UPDATE enrollments SET passing_grade=COALESCE((SELECT passing_grade FROM institution_settings WHERE settings_id=1),70) WHERE passing_grade IS NULL"
        )
    )
    op.create_table(
        "governance_control",
        sa.Column("governance_control_id", sa.Integer(), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False),
    )
    op.execute(
        sa.text("INSERT INTO governance_control (governance_control_id,version) VALUES (1,0)")
    )


def downgrade():
    raise RuntimeError(
        "No se elimina automáticamente la trazabilidad ni los criterios históricos; restaurar un respaldo de forma controlada."
    )
