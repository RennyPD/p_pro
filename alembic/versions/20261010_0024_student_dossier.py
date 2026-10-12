"""Add optional student identification, admission and emergency details."""

import sqlalchemy as sa
from alembic import op

revision = "20261010_0024"
down_revision = "20260922_0023"
branch_labels = None
depends_on = None

FIELDS = {
    "document_number": sa.String(50),
    "birth_date": sa.Date(),
    "nationality": sa.String(100),
    "admission_date": sa.Date(),
    "previous_school": sa.String(255),
    "emergency_contact_name": sa.String(150),
    "emergency_contact_phone": sa.String(30),
    "emergency_contact_relationship": sa.String(60),
}


def upgrade() -> None:
    for name, kind in FIELDS.items():
        op.add_column("students", sa.Column(name, kind, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("students") as batch:
        for name in reversed(FIELDS):
            batch.drop_column(name)
