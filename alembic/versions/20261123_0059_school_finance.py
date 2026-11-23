"""School finance: grade plans, family discount, late fees, holds (Fase 3, block E).

- billing_plans: school_year_id and sibling_discount.
- billing_plan_targets: grade_number (kind "grade"); the unique target now
  includes it so one plan can list several grades of a program.
- billing_runs.created_by and finance_events.user_id may be empty: the
  scheduled daily job acts as "sistema".
- financial_adjustments: charge_id and a unique automation_key, so automatic
  discounts and late fees are never posted twice.
- students.financial_hold_source: "auto" when the daily job set the hold.
- finance_policies: one row, everything disabled until configured.

Revision ID: 20261123_0059
Revises: 20261123_0058
"""

import sqlalchemy as sa

from alembic import op

revision = "20261123_0059"
down_revision = "20261123_0058"
branch_labels = None
depends_on = None

MONEY = sa.Numeric(12, 2)


def upgrade() -> None:
    with op.batch_alter_table("billing_plans") as batch:
        batch.add_column(sa.Column("school_year_id", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column("sibling_discount", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch.create_foreign_key(
            "fk_billing_plans_school_year", "school_years", ["school_year_id"], ["school_year_id"]
        )
        batch.create_index("ix_billing_plans_school_year_id", ["school_year_id"])
    with op.batch_alter_table("billing_plan_targets") as batch:
        batch.add_column(sa.Column("grade_number", sa.Integer(), nullable=True))
        batch.drop_constraint("uq_plan_target", type_="unique")
        batch.create_unique_constraint(
            "uq_plan_target",
            ["billing_plan_id", "kind", "career_id", "grade_number", "student_id"],
        )
    with op.batch_alter_table("billing_runs") as batch:
        batch.alter_column("created_by", existing_type=sa.Integer(), nullable=True)
    with op.batch_alter_table("finance_events") as batch:
        batch.alter_column("user_id", existing_type=sa.Integer(), nullable=True)
    with op.batch_alter_table("financial_adjustments") as batch:
        batch.add_column(sa.Column("charge_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("automation_key", sa.String(80), nullable=True))
        batch.create_foreign_key(
            "fk_financial_adjustments_charge", "charges", ["charge_id"], ["charge_id"]
        )
        batch.create_index("ix_financial_adjustments_charge_id", ["charge_id"])
        batch.create_unique_constraint(
            "uq_financial_adjustments_automation_key", ["automation_key"]
        )
    with op.batch_alter_table("students") as batch:
        batch.add_column(sa.Column("financial_hold_source", sa.String(10), nullable=True))
    op.create_table(
        "finance_policies",
        sa.Column("finance_policy_id", sa.Integer(), primary_key=True),
        sa.Column("late_fee_enabled", sa.Boolean(), nullable=False),
        sa.Column("grace_days", sa.Integer(), nullable=False),
        sa.Column("late_fee_kind", sa.String(10), nullable=False),
        sa.Column("late_fee_value", MONEY, nullable=False),
        sa.Column("hold_enabled", sa.Boolean(), nullable=False),
        sa.Column("hold_after_days", sa.Integer(), nullable=False),
        sa.Column("hold_min_amount", MONEY, nullable=False),
        sa.Column("sibling_discount_enabled", sa.Boolean(), nullable=False),
        sa.Column("sibling_second_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("sibling_third_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("auto_billing_enabled", sa.Boolean(), nullable=False),
        sa.Column("billing_lead_days", sa.Integer(), nullable=False),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("finance_policies")
    with op.batch_alter_table("students") as batch:
        batch.drop_column("financial_hold_source")
    with op.batch_alter_table("financial_adjustments") as batch:
        batch.drop_constraint("uq_financial_adjustments_automation_key", type_="unique")
        batch.drop_index("ix_financial_adjustments_charge_id")
        batch.drop_constraint("fk_financial_adjustments_charge", type_="foreignkey")
        batch.drop_column("automation_key")
        batch.drop_column("charge_id")
    # Rows written by the daily job have no user; they cannot satisfy NOT NULL again.
    op.execute("DELETE FROM billing_runs WHERE created_by IS NULL")
    op.execute("DELETE FROM finance_events WHERE user_id IS NULL")
    with op.batch_alter_table("finance_events") as batch:
        batch.alter_column("user_id", existing_type=sa.Integer(), nullable=False)
    with op.batch_alter_table("billing_runs") as batch:
        batch.alter_column("created_by", existing_type=sa.Integer(), nullable=False)
    op.execute("DELETE FROM billing_plan_targets WHERE kind = 'grade'")
    with op.batch_alter_table("billing_plan_targets") as batch:
        batch.drop_constraint("uq_plan_target", type_="unique")
        batch.create_unique_constraint(
            "uq_plan_target", ["billing_plan_id", "kind", "career_id", "student_id"]
        )
        batch.drop_column("grade_number")
    with op.batch_alter_table("billing_plans") as batch:
        batch.drop_index("ix_billing_plans_school_year_id")
        batch.drop_constraint("fk_billing_plans_school_year", type_="foreignkey")
        batch.drop_column("sibling_discount")
        batch.drop_column("school_year_id")
