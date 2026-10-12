"""Versioned equivalences, activation and accountable updates."""

import sqlalchemy as sa

from alembic import op

revision = "20261012_0030"
down_revision = "20261012_0029"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("course_equivalences") as batch:
        batch.drop_constraint("uq_course_equivalence", type_="unique")
        batch.create_unique_constraint(
            "uq_course_equivalence",
            ["career_id", "source_subject_id", "target_subject_id", "curriculum_version"],
        )
        batch.add_column(
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true())
        )
        batch.add_column(sa.Column("created_by", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("updated_by", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("updated_at", sa.DateTime(), nullable=True))
        batch.create_foreign_key("fk_equivalence_creator", "users", ["created_by"], ["user_id"])
        batch.create_foreign_key("fk_equivalence_editor", "users", ["updated_by"], ["user_id"])


def downgrade():
    duplicates = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT career_id, source_subject_id, target_subject_id FROM course_equivalences GROUP BY career_id,source_subject_id,target_subject_id HAVING COUNT(*)>1"
            )
        )
        .first()
    )
    if duplicates:
        raise RuntimeError(
            "Existen reglas en varias versiones; no se eliminan para hacer downgrade."
        )
    with op.batch_alter_table("course_equivalences") as batch:
        batch.drop_constraint("fk_equivalence_creator", type_="foreignkey")
        batch.drop_constraint("fk_equivalence_editor", type_="foreignkey")
        batch.drop_constraint("uq_course_equivalence", type_="unique")
        batch.create_unique_constraint(
            "uq_course_equivalence", ["career_id", "source_subject_id", "target_subject_id"]
        )
        for field in ("active", "created_by", "updated_by", "updated_at"):
            batch.drop_column(field)
