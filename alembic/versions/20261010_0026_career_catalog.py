"""Institutional career catalogue."""

import sqlalchemy as sa

from alembic import op

revision = "20261010_0026"
down_revision = "20261010_0025"
branch_labels = None
depends_on = None
FIELDS = {
    "faculty": sa.String(150),
    "department": sa.String(150),
    "coordinator_name": sa.String(150),
    "contact_email": sa.String(255),
    "campus": sa.String(150),
    "authorization_reference": sa.String(150),
    "admission_profile": sa.Text(),
    "graduate_profile": sa.Text(),
    "professional_fields": sa.Text(),
    "admission_requirements": sa.Text(),
    "graduation_requirements": sa.Text(),
}


def upgrade():
    op.add_column(
        "careers", sa.Column("status", sa.String(20), nullable=False, server_default="active")
    )
    op.add_column(
        "careers", sa.Column("modality", sa.String(20), nullable=False, server_default="in_person")
    )
    for name, kind in FIELDS.items():
        op.add_column("careers", sa.Column(name, kind, nullable=True))


def downgrade():
    with op.batch_alter_table("careers") as batch:
        for name in [*FIELDS, "status", "modality"]:
            batch.drop_column(name)
