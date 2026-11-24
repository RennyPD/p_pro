"""Subscription payments (Fase 4, block D2).

- billing_events: provider events already processed (idempotent webhooks).
- subscriptions.last_event_at: late events never undo newer ones.
- Permission billing.manage, granted to every role that already holds
  settings.manage (institutions that saved their permissions keep working).

Revision ID: 20261125_0067
Revises: 20261125_0066
"""

import sqlalchemy as sa

from alembic import op

revision = "20261125_0067"
down_revision = "20261125_0066"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "billing_events",
        sa.Column("billing_event_id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("event_id", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column(
            "institution_id",
            sa.Integer(),
            sa.ForeignKey("institutions.institution_id", name="fk_billing_events_institution"),
            nullable=True,
        ),
        sa.Column("outcome", sa.String(200), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("provider", "event_id", name="uq_billing_events_provider_event"),
    )
    with op.batch_alter_table("subscriptions") as batch:
        batch.add_column(sa.Column("last_event_at", sa.DateTime(), nullable=True))
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "INSERT INTO permissions (slug, description) "
            "SELECT 'billing.manage', 'Gestionar plan y facturación' "
            "WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE slug = 'billing.manage')"
        )
    )
    connection.execute(
        sa.text(
            "INSERT INTO role_permissions (institution_id, role_id, permission_id) "
            "SELECT rp.institution_id, rp.role_id, billing.permission_id "
            "FROM role_permissions rp "
            "JOIN permissions settings ON settings.permission_id = rp.permission_id "
            "AND settings.slug = 'settings.manage' "
            "CROSS JOIN permissions billing "
            "WHERE billing.slug = 'billing.manage' AND NOT EXISTS ("
            "  SELECT 1 FROM role_permissions existing "
            "  WHERE existing.role_id = rp.role_id "
            "  AND existing.permission_id = billing.permission_id)"
        )
    )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN "
            "(SELECT permission_id FROM permissions WHERE slug = 'billing.manage')"
        )
    )
    connection.execute(sa.text("DELETE FROM permissions WHERE slug = 'billing.manage'"))
    with op.batch_alter_table("subscriptions") as batch:
        batch.drop_column("last_event_at")
    op.drop_table("billing_events")
