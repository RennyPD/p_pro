"""Add optional attachments to individual submission attempts."""

import sqlalchemy as sa

from alembic import op

revision = "20261117_0035"
down_revision = "20261117_0034"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "submission_attachments",
        sa.Column(
            "revision_id",
            sa.Integer(),
            sa.ForeignKey("submission_revisions.revision_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
    )


def downgrade():
    op.drop_table("submission_attachments")
