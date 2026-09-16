"""Add refresh sessions and audit log."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260916_0004"
down_revision: Union[str, None] = "20260916_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table("refresh_tokens", sa.Column("refresh_token_id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=False), sa.Column("token_hash", sa.String(64), nullable=False, unique=True), sa.Column("expires_at", sa.DateTime(), nullable=False), sa.Column("revoked_at", sa.DateTime(), nullable=True), sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True)
    op.create_table("audit_logs", sa.Column("audit_log_id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=True), sa.Column("action", sa.String(80), nullable=False), sa.Column("resource", sa.String(80), nullable=False), sa.Column("detail", sa.String(500), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("refresh_tokens")
