"""Billing plans: recurring charges (monthly tuition) generated per cycle.

Adds billing_plans, billing_plan_targets and billing_runs, and links generated
charges to their plan and cycle. The unique (account, plan, cycle) constraint
guarantees a plan never charges the same account twice for the same month.

Revision ID: 20261120_0047
Revises: 20261120_0046
"""

import sqlalchemy as sa

from alembic import op

revision = "20261120_0047"
down_revision = "20261120_0046"
branch_labels = None
depends_on = None

MONEY = sa.Numeric(12, 2)


def upgrade() -> None:
    op.create_table(
        "billing_plans",
        sa.Column("billing_plan_id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("charge_description", sa.String(150), nullable=False),
        sa.Column(
            "billing_concept_id",
            sa.Integer(),
            sa.ForeignKey("billing_concepts.billing_concept_id"),
            nullable=True,
        ),
        sa.Column("amount", MONEY, nullable=False),
        sa.Column("frequency", sa.String(20), nullable=False),
        sa.Column("start_month", sa.Date(), nullable=False),
        sa.Column("end_month", sa.Date(), nullable=False),
        sa.Column("due_day", sa.Integer(), nullable=False),
        sa.Column(
            "period_id", sa.Integer(), sa.ForeignKey("academic_periods.period_id"), nullable=True
        ),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "billing_plan_targets",
        sa.Column("billing_plan_target_id", sa.Integer(), primary_key=True),
        sa.Column(
            "billing_plan_id",
            sa.Integer(),
            sa.ForeignKey("billing_plans.billing_plan_id"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("career_id", sa.Integer(), sa.ForeignKey("careers.career_id"), nullable=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.student_id"), nullable=True),
        sa.UniqueConstraint(
            "billing_plan_id", "kind", "career_id", "student_id", name="uq_plan_target"
        ),
    )
    op.create_table(
        "billing_runs",
        sa.Column("billing_run_id", sa.Integer(), primary_key=True),
        sa.Column(
            "billing_plan_id",
            sa.Integer(),
            sa.ForeignKey("billing_plans.billing_plan_id"),
            nullable=False,
        ),
        sa.Column("cycle", sa.String(7), nullable=False),
        sa.Column("charge_count", sa.Integer(), nullable=False),
        sa.Column("total", MONEY, nullable=False),
        sa.Column("reason", sa.String(250), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=True, unique=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    with op.batch_alter_table("charges") as batch:
        batch.add_column(sa.Column("billing_plan_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("billing_cycle", sa.String(7), nullable=True))
        batch.create_foreign_key(
            "fk_charges_billing_plan", "billing_plans", ["billing_plan_id"], ["billing_plan_id"]
        )
        batch.create_unique_constraint(
            "uq_charges_plan_cycle", ["student_account_id", "billing_plan_id", "billing_cycle"]
        )


def downgrade() -> None:
    with op.batch_alter_table("charges") as batch:
        batch.drop_constraint("uq_charges_plan_cycle", type_="unique")
        batch.drop_constraint("fk_charges_billing_plan", type_="foreignkey")
        batch.drop_column("billing_cycle")
        batch.drop_column("billing_plan_id")
    op.drop_table("billing_runs")
    op.drop_table("billing_plan_targets")
    op.drop_table("billing_plans")
