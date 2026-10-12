"""Internal payments, protected proofs and finance audit without deleting legacy data."""

import sqlalchemy as sa

from alembic import op

revision = "20261012_0031"
down_revision = "20261012_0030"
branch_labels = None
depends_on = None


def upgrade():
    columns = {
        "student_accounts": [
            sa.Column("ledger_version", sa.Integer(), nullable=False, server_default="0")
        ],
        "charges": [
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="posted"),
            sa.Column("reversal_reason", sa.String(250), nullable=True),
        ],
        "payments": [
            sa.Column("method", sa.String(20), nullable=False, server_default="legacy"),
            sa.Column("status", sa.String(20), nullable=False, server_default="posted"),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("reversed_by", sa.Integer(), nullable=True),
            sa.Column("reversed_at", sa.DateTime(), nullable=True),
            sa.Column("reversal_reason", sa.String(250), nullable=True),
            sa.Column("idempotency_key", sa.String(100), nullable=True),
        ],
        "financial_adjustments": [
            sa.Column("due_date", sa.Date(), nullable=True),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="posted"),
            sa.Column("reversal_reason", sa.String(250), nullable=True),
        ],
        "payment_plans": [
            sa.Column("credit_snapshot", sa.Float(), nullable=True),
            sa.Column("credit_baseline", sa.Float(), nullable=False, server_default="0"),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        ],
        "cash_closings": [
            sa.Column("cash_total", sa.Float(), nullable=False, server_default="0"),
            sa.Column("transfer_total", sa.Float(), nullable=False, server_default="0"),
        ],
    }
    for table, fields in columns.items():
        with op.batch_alter_table(table) as batch:
            for column in fields:
                batch.add_column(column)
            for field in ("created_by", "reversed_by"):
                if field in {c.name for c in fields}:
                    batch.create_foreign_key(f"fk_{table}_{field}", "users", [field], ["user_id"])
            if table == "payments":
                batch.create_unique_constraint("uq_payment_idempotency", ["idempotency_key"])
    from app.models.finance_model import FinanceControl, FinanceEvent, TransferRequest

    for table in (TransferRequest.__table__, FinanceEvent.__table__, FinanceControl.__table__):
        table.create(op.get_bind())
    op.execute(sa.text("INSERT INTO finance_control (finance_control_id, version) VALUES (1,0)"))
    # Legacy plans retain their initial paid flags; only subsequent credits enter new tracking.
    op.execute(
        sa.text(
            "UPDATE payment_plans SET credit_baseline = COALESCE((SELECT SUM(amount) FROM payments WHERE student_account_id=payment_plans.student_account_id),0) + COALESCE((SELECT SUM(amount) FROM financial_adjustments WHERE student_account_id=payment_plans.student_account_id AND kind IN ('discount','scholarship','credit')),0)"
        )
    )


def downgrade():
    raise RuntimeError(
        "Esta migración financiera no se revierte automáticamente: preservar comprobantes, pagos y auditoría requiere una restauración controlada desde respaldo."
    )
