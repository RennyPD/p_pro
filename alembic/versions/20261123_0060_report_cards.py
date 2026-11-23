"""Report cards: MINERD identification of the school and homeroom remarks (Fase 3 F).

Revision ID: 20261123_0060
Revises: 20261123_0059
"""

import sqlalchemy as sa

from alembic import op

revision = "20261123_0060"
down_revision = "20261123_0059"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("institution_settings") as batch:
        batch.add_column(sa.Column("school_code", sa.String(30), nullable=False, server_default=""))
        batch.add_column(sa.Column("regional", sa.String(80), nullable=False, server_default=""))
        batch.add_column(sa.Column("district", sa.String(80), nullable=False, server_default=""))
    op.create_table(
        "report_card_comments",
        sa.Column("report_card_comment_id", sa.Integer(), primary_key=True),
        sa.Column(
            "member_id",
            sa.Integer(),
            sa.ForeignKey("class_group_members.member_id"),
            nullable=False,
        ),
        sa.Column(
            "period_id", sa.Integer(), sa.ForeignKey("academic_periods.period_id"), nullable=False
        ),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("member_id", "period_id", name="uq_report_card_comment"),
    )
    op.create_index("ix_report_card_comments_member_id", "report_card_comments", ["member_id"])


def downgrade() -> None:
    op.drop_table("report_card_comments")
    with op.batch_alter_table("institution_settings") as batch:
        batch.drop_column("district")
        batch.drop_column("regional")
        batch.drop_column("school_code")
