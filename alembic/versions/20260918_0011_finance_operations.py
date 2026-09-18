"""Add adjustments, payment plans, installments and receipt numbers."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260918_0011"
down_revision: Union[str, None] = "20260918_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("receipt_number", sa.String(100), nullable=True))
    with op.batch_alter_table("payments") as batch:
        batch.create_unique_constraint("uq_payments_receipt_number", ["receipt_number"])
    op.create_table(
        "financial_adjustments",
        sa.Column("adjustment_id", sa.Integer(), primary_key=True),
        sa.Column("student_account_id", sa.Integer(), sa.ForeignKey("student_accounts.student_account_id"), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("description", sa.String(200), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "payment_plans",
        sa.Column("payment_plan_id", sa.Integer(), primary_key=True),
        sa.Column("student_account_id", sa.Integer(), sa.ForeignKey("student_accounts.student_account_id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "installments",
        sa.Column("installment_id", sa.Integer(), primary_key=True),
        sa.Column("payment_plan_id", sa.Integer(), sa.ForeignKey("payment_plans.payment_plan_id"), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("paid", sa.Boolean(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("installments")
    op.drop_table("payment_plans")
    op.drop_table("financial_adjustments")
    with op.batch_alter_table("payments") as batch:
        batch.drop_constraint("uq_payments_receipt_number", type_="unique")
        batch.drop_column("receipt_number")
