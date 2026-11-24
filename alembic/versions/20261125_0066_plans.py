"""SaaS plans and subscriptions (Fase 4, block D1).

Global tables. Seeds three editable plans (prices and limits are changed from
the platform panel) and gives every existing institution an active
subscription to the unlimited «Institucional» plan, so nothing changes for
installations that already work.

Revision ID: 20261125_0066
Revises: 20261125_0065
"""

from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision = "20261125_0066"
down_revision = "20261125_0065"
branch_labels = None
depends_on = None

PLANS = (
    # code, name, description, monthly, yearly, students, staff, storage GB, public, order
    ("basico", "Básico", "Centros pequeños", "99.00", "990.00", 300, 30, 10, True, 1),
    ("profesional", "Profesional", "Colegios y universidades medianos", "249.00", "2490.00", 1500, 150, 50, True, 2),
    ("institucional", "Institucional", "A medida, sin límites", "0.00", "0.00", None, None, None, False, 3),
)  # fmt: skip


def upgrade() -> None:
    plans = op.create_table(
        "plans",
        sa.Column("plan_id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("description", sa.String(300), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("monthly_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("yearly_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("max_students", sa.Integer(), nullable=True),
        sa.Column("max_staff", sa.Integer(), nullable=True),
        sa.Column("storage_gb", sa.Integer(), nullable=True),
        sa.Column("public", sa.Boolean(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("provider_monthly_price", sa.String(120), nullable=True),
        sa.Column("provider_yearly_price", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("code", name="uq_plans_code"),
    )
    op.create_table(
        "subscriptions",
        sa.Column("subscription_id", sa.Integer(), primary_key=True),
        sa.Column(
            "institution_id",
            sa.Integer(),
            sa.ForeignKey("institutions.institution_id", name="fk_subscriptions_institution"),
            nullable=False,
        ),
        sa.Column(
            "plan_id",
            sa.Integer(),
            sa.ForeignKey("plans.plan_id", name="fk_subscriptions_plan"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("interval", sa.String(10), nullable=False),
        sa.Column("trial_ends_at", sa.DateTime(), nullable=True),
        sa.Column("current_period_end", sa.DateTime(), nullable=True),
        sa.Column("past_due_since", sa.DateTime(), nullable=True),
        sa.Column("read_only_since", sa.DateTime(), nullable=True),
        sa.Column("canceled_at", sa.DateTime(), nullable=True),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("provider_customer_id", sa.String(120), nullable=True),
        sa.Column("provider_subscription_id", sa.String(120), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("institution_id", name="uq_subscriptions_institution_id"),
    )
    connection = op.get_bind()
    now = datetime.now(UTC).replace(tzinfo=None)
    op.bulk_insert(
        plans,
        [
            {
                "code": code,
                "name": name,
                "description": description,
                "currency": "USD",
                "monthly_price": monthly,
                "yearly_price": yearly,
                "max_students": students,
                "max_staff": staff,
                "storage_gb": storage,
                "public": public,
                "active": True,
                "sort_order": order,
                "created_at": now,
            }
            for code, name, description, monthly, yearly, students, staff, storage, public, order in PLANS
        ],
    )
    connection.execute(
        sa.text(
            "INSERT INTO subscriptions (institution_id, plan_id, status, interval, provider, updated_at) "
            "SELECT i.institution_id, p.plan_id, 'active', 'yearly', 'manual', CURRENT_TIMESTAMP "
            "FROM institutions i, plans p WHERE p.code = 'institucional'"
        )
    )


def downgrade() -> None:
    op.drop_table("subscriptions")
    op.drop_table("plans")
