"""Add university catalog metadata to careers and periods.

Revision ID: 20260918_0015
Revises: 20260918_0014
"""

import sqlalchemy as sa
from alembic import op

revision = "20260918_0015"
down_revision = "20260918_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("careers") as batch:
        batch.add_column(sa.Column("code", sa.String(30), nullable=True))
        batch.add_column(sa.Column("academic_level", sa.String(30), nullable=False, server_default="undergraduate"))
        batch.add_column(sa.Column("degree_title", sa.String(150), nullable=False, server_default=""))
        batch.add_column(sa.Column("term_type", sa.String(20), nullable=False, server_default="semester"))
        batch.add_column(sa.Column("duration_terms", sa.Integer(), nullable=False, server_default="8"))
    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT career_id FROM careers ORDER BY career_id")).fetchall()
    for sequence, row in enumerate(rows, start=1):
        connection.execute(sa.text("UPDATE careers SET code = :code WHERE career_id = :id"), {"code": f"CAR-{sequence:03d}", "id": row[0]})
    with op.batch_alter_table("careers") as batch:
        batch.alter_column("code", nullable=False)
        batch.create_unique_constraint("uq_careers_code", ["code"])
    with op.batch_alter_table("academic_periods") as batch:
        batch.add_column(sa.Column("period_type", sa.String(20), nullable=False, server_default="semester"))
        batch.add_column(sa.Column("sequence", sa.Integer(), nullable=False, server_default="1"))
        batch.add_column(sa.Column("academic_year", sa.String(20), nullable=False, server_default=""))
    op.execute("UPDATE academic_periods SET academic_year = name")
    op.execute("UPDATE academic_periods SET status = 'active' WHERE active = 1 AND status = 'planning'")


def downgrade() -> None:
    with op.batch_alter_table("academic_periods") as batch:
        batch.drop_column("academic_year")
        batch.drop_column("sequence")
        batch.drop_column("period_type")
    with op.batch_alter_table("careers") as batch:
        batch.drop_constraint("uq_careers_code", type_="unique")
        batch.drop_column("duration_terms")
        batch.drop_column("term_type")
        batch.drop_column("degree_title")
        batch.drop_column("academic_level")
        batch.drop_column("code")
