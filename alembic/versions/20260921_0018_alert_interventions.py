"""Add alert ownership and intervention history.

Revision ID: 20260921_0018
Revises: 20260921_0017
"""
import sqlalchemy as sa
from alembic import op

revision = "20260921_0018"
down_revision = "20260921_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("early_alerts") as batch:
        batch.add_column(sa.Column("assigned_to", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("follow_up_date", sa.Date(), nullable=True))
        batch.add_column(sa.Column("resolution_notes", sa.Text(), nullable=False, server_default=""))
        batch.create_foreign_key("fk_early_alerts_assigned_to_users", "users", ["assigned_to"], ["user_id"])
    op.create_table(
        "alert_interventions",
        sa.Column("alert_intervention_id", sa.Integer(), primary_key=True),
        sa.Column("early_alert_id", sa.Integer(), sa.ForeignKey("early_alerts.early_alert_id"), nullable=False),
        sa.Column("action_type", sa.String(30), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("performed_by", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("alert_interventions")
    with op.batch_alter_table("early_alerts") as batch:
        batch.drop_constraint("fk_early_alerts_assigned_to_users", type_="foreignkey")
        batch.drop_column("resolution_notes")
        batch.drop_column("follow_up_date")
        batch.drop_column("assigned_to")
