"""Add optional professional and institutional teacher dossier fields."""

import sqlalchemy as sa
from alembic import op

revision = "20261010_0025"
down_revision = "20261010_0024"
branch_labels = None
depends_on = None

FIELDS = {
    "employee_code": sa.String(50),
    "document_number": sa.String(50),
    "birth_date": sa.Date(),
    "nationality": sa.String(100),
    "academic_degree": sa.String(150),
    "alma_mater": sa.String(255),
    "professional_license": sa.String(100),
    "experience_years": sa.Integer(),
    "department": sa.String(150),
    "teaching_category": sa.String(100),
    "employment_type": sa.String(30),
    "appointment_date": sa.Date(),
    "emergency_contact_name": sa.String(150),
    "emergency_contact_phone": sa.String(30),
    "emergency_contact_relationship": sa.String(60),
}


def upgrade() -> None:
    for name, kind in FIELDS.items():
        op.add_column("teachers", sa.Column(name, kind, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("teachers") as batch:
        for name in reversed(FIELDS):
            batch.drop_column(name)
