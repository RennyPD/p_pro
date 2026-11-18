"""Store money as NUMERIC(12, 2) instead of FLOAT (audit, low findings).

Values are rounded half-up to cents. Amounts were always validated with at
most two decimals, so rounding only removes binary floating point noise.
"""

import sqlalchemy as sa

from alembic import op

revision = "20261118_0042"
down_revision = "20261118_0041"
branch_labels = None
depends_on = None

MONEY_COLUMNS = {
    "charges": ["amount"],
    "payments": ["amount"],
    "financial_adjustments": ["amount"],
    "payment_plans": ["credit_baseline", "credit_snapshot"],
    "installments": ["amount"],
    "billing_concepts": ["amount"],
    "cash_closings": ["total_payments", "cash_total", "transfer_total"],
}


def upgrade():
    postgresql = op.get_bind().dialect.name == "postgresql"
    for table, columns in MONEY_COLUMNS.items():
        if not postgresql:
            # SQLite: round in place first; the table rebuild keeps the values.
            for column in columns:
                op.execute(sa.text(f"UPDATE {table} SET {column} = ROUND({column}, 2)"))
        with op.batch_alter_table(table) as batch:
            for column in columns:
                batch.alter_column(
                    column,
                    existing_type=sa.Float(),
                    type_=sa.Numeric(12, 2),
                    postgresql_using=f"round({column}::numeric, 2)",
                )


def downgrade():
    for table, columns in MONEY_COLUMNS.items():
        with op.batch_alter_table(table) as batch:
            for column in columns:
                batch.alter_column(
                    column,
                    existing_type=sa.Numeric(12, 2),
                    type_=sa.Float(),
                    postgresql_using=f"{column}::double precision",
                )
