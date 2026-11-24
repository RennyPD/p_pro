"""Online card payments of families (Fase 4, block E1).

- online_payments: payment intents sent to the institution's gateway.
- payment_gateway_configs: the institution's own merchant account (secrets
  encrypted with PAYMENTS_ENCRYPTION_KEY).
Both belong to an institution: institution_id and Row-Level Security.

Revision ID: 20261126_0068
Revises: 20261125_0067
"""

import sqlalchemy as sa

from alembic import op

revision = "20261126_0068"
down_revision = "20261125_0067"
branch_labels = None
depends_on = None

POLICY = (
    "current_setting('app.tenant_bypass', true) = 'on' OR institution_id = "
    "NULLIF(current_setting('app.institution_id', true), '')::integer"
)
MONEY = sa.Numeric(12, 2)


def institution_column(table: str) -> sa.Column:
    return sa.Column(
        "institution_id",
        sa.Integer(),
        sa.ForeignKey("institutions.institution_id", name=f"fk_{table}_institution"),
        nullable=False,
        index=True,
    )


def upgrade() -> None:
    op.create_table(
        "online_payments",
        sa.Column("online_payment_id", sa.Integer(), primary_key=True),
        institution_column("online_payments"),
        sa.Column("public_id", sa.String(32), nullable=False),
        sa.Column("payer_user_id", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("gateway", sa.String(20), nullable=False),
        sa.Column("amount", MONEY, nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("allocations", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("provider_reference", sa.String(100), nullable=True),
        sa.Column("authorization_code", sa.String(40), nullable=True),
        sa.Column("response_code", sa.String(20), nullable=True),
        sa.Column("response_message", sa.String(250), nullable=True),
        sa.Column("payment_ids", sa.String(200), nullable=False),
        sa.Column("overpaid", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_online_payments_public_id", "online_payments", ["public_id"], unique=True)
    op.create_index("ix_online_payments_status", "online_payments", ["status"])
    op.create_table(
        "payment_gateway_configs",
        sa.Column("payment_gateway_config_id", sa.Integer(), primary_key=True),
        institution_column("payment_gateway_configs"),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("gateway", sa.String(20), nullable=False),
        sa.Column("merchant_id", sa.String(60), nullable=False),
        sa.Column("merchant_name", sa.String(100), nullable=False),
        sa.Column("secrets", sa.Text(), nullable=False),
        sa.Column("min_amount", MONEY, nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=True),
        sa.UniqueConstraint("institution_id", name="uq_payment_gateway_configs_institution"),
    )
    if op.get_bind().dialect.name == "postgresql":
        for table in ("online_payments", "payment_gateway_configs"):
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(
                f"CREATE POLICY tenant_isolation ON {table} USING ({POLICY}) WITH CHECK ({POLICY})"
            )


def downgrade() -> None:
    op.drop_table("payment_gateway_configs")
    op.drop_index("ix_online_payments_status", table_name="online_payments")
    op.drop_index("ix_online_payments_public_id", table_name="online_payments")
    op.drop_table("online_payments")
