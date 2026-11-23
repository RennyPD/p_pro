"""Official MINERD secondary report card (Fase 3 F2).

- competency_groups with the four MINERD groups of fundamental competencies;
  assessments.competency_group_id links each period assessment to its group.
- careers.report_card_format: general | minerd_secondary.
- students.sigerd_id, class_groups.shift (tanda) and the school's phone,
  province and municipality for the report card header.

Revision ID: 20261123_0061
Revises: 20261123_0060
"""

import sqlalchemy as sa

from alembic import op

revision = "20261123_0061"
down_revision = "20261123_0060"
branch_labels = None
depends_on = None

GROUPS = (
    (1, "Comunicativa", "Comunicativa"),
    (
        2,
        "Pensamiento Lógico, Creativo y Crítico · Resolución de Problemas",
        "Pensamiento y resolución",
    ),
    (3, "Científica y Tecnológica · Ambiental y de la Salud", "Científica y ambiental"),
    (4, "Ética y Ciudadana · Desarrollo Personal y Espiritual", "Ética y desarrollo personal"),
)


def upgrade() -> None:
    table = op.create_table(
        "competency_groups",
        sa.Column("competency_group_id", sa.Integer(), primary_key=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("short_name", sa.String(40), nullable=False),
        sa.UniqueConstraint("position", name="uq_competency_groups_position"),
    )
    op.bulk_insert(
        table,
        [{"position": p, "name": name, "short_name": short} for p, name, short in GROUPS],
    )
    with op.batch_alter_table("assessments") as batch:
        batch.add_column(sa.Column("competency_group_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_assessments_competency_group",
            "competency_groups",
            ["competency_group_id"],
            ["competency_group_id"],
        )
    with op.batch_alter_table("careers") as batch:
        batch.add_column(
            sa.Column("report_card_format", sa.String(30), nullable=False, server_default="general")
        )
    with op.batch_alter_table("students") as batch:
        batch.add_column(sa.Column("sigerd_id", sa.String(30), nullable=True))
    with op.batch_alter_table("class_groups") as batch:
        batch.add_column(sa.Column("shift", sa.String(20), nullable=False, server_default=""))
    with op.batch_alter_table("institution_settings") as batch:
        batch.add_column(
            sa.Column("school_phone", sa.String(30), nullable=False, server_default="")
        )
        batch.add_column(sa.Column("province", sa.String(80), nullable=False, server_default=""))
        batch.add_column(
            sa.Column("municipality", sa.String(80), nullable=False, server_default="")
        )


def downgrade() -> None:
    with op.batch_alter_table("institution_settings") as batch:
        batch.drop_column("municipality")
        batch.drop_column("province")
        batch.drop_column("school_phone")
    with op.batch_alter_table("class_groups") as batch:
        batch.drop_column("shift")
    with op.batch_alter_table("students") as batch:
        batch.drop_column("sigerd_id")
    with op.batch_alter_table("careers") as batch:
        batch.drop_column("report_card_format")
    with op.batch_alter_table("assessments") as batch:
        batch.drop_constraint("fk_assessments_competency_group", type_="foreignkey")
        batch.drop_column("competency_group_id")
    op.drop_table("competency_groups")
