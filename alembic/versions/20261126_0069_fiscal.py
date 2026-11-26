"""Fiscal receipts (Fase 4, block F1-F2).

- fiscal_profiles (issuer data), fiscal_sequences (DGII ranges),
  fiscal_documents and fiscal_document_lines, all per institution with RLS.
- student_accounts.bill_to_name / bill_to_tax_id.
- billing_concepts.itbis_rate and charges.itbis_rate (0 = exempt).

Revision ID: 20261126_0069
Revises: 20261126_0068
"""

import sqlalchemy as sa

from alembic import op

revision = "20261126_0069"
down_revision = "20261126_0068"
branch_labels = None
depends_on = None

POLICY = (
    "current_setting('app.tenant_bypass', true) = 'on' OR institution_id = "
    "NULLIF(current_setting('app.institution_id', true), '')::integer"
)
MONEY = sa.Numeric(12, 2)
RATE = sa.Numeric(5, 2)
TABLES = ("fiscal_profiles", "fiscal_sequences", "fiscal_documents", "fiscal_document_lines")


def institution(table: str) -> sa.Column:
    return sa.Column(
        "institution_id",
        sa.Integer(),
        sa.ForeignKey("institutions.institution_id", name=f"fk_{table}_institution"),
        nullable=False,
        index=True,
    )


def users(name: str) -> sa.Column:
    return sa.Column(name, sa.Integer(), sa.ForeignKey("users.user_id"), nullable=True)


def upgrade() -> None:
    op.create_table(
        "fiscal_profiles",
        sa.Column("fiscal_profile_id", sa.Integer(), primary_key=True),
        institution("fiscal_profiles"),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("mode", sa.String(10), nullable=False),
        sa.Column("rnc", sa.String(11), nullable=False),
        sa.Column("legal_name", sa.String(150), nullable=False),
        sa.Column("trade_name", sa.String(150), nullable=False),
        sa.Column("fiscal_address", sa.String(250), nullable=False),
        sa.Column("issue_on", sa.String(10), nullable=False),
        sa.Column("ecf_provider", sa.String(30), nullable=False),
        sa.Column("ecf_secrets", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        users("updated_by"),
        sa.UniqueConstraint("institution_id", name="uq_fiscal_profiles_institution"),
    )
    op.create_table(
        "fiscal_sequences",
        sa.Column("fiscal_sequence_id", sa.Integer(), primary_key=True),
        institution("fiscal_sequences"),
        sa.Column("doc_type", sa.String(3), nullable=False),
        sa.Column("range_start", sa.Integer(), nullable=False),
        sa.Column("range_end", sa.Integer(), nullable=False),
        sa.Column("next_number", sa.Integer(), nullable=False),
        sa.Column("expires_on", sa.Date(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        users("created_by"),
        sa.UniqueConstraint(
            "institution_id", "doc_type", "range_start", name="uq_fiscal_sequences_range"
        ),
    )
    op.create_table(
        "fiscal_documents",
        sa.Column("fiscal_document_id", sa.Integer(), primary_key=True),
        institution("fiscal_documents"),
        sa.Column("doc_type", sa.String(3), nullable=False),
        sa.Column("ncf", sa.String(19), nullable=False),
        sa.Column(
            "fiscal_sequence_id",
            sa.Integer(),
            sa.ForeignKey("fiscal_sequences.fiscal_sequence_id"),
            nullable=True,
        ),
        sa.Column("sequence_expires_on", sa.Date(), nullable=True),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("issued_at", sa.DateTime(), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.student_id"), nullable=True),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.payment_id"), nullable=True),
        sa.Column(
            "affected_document_id",
            sa.Integer(),
            sa.ForeignKey("fiscal_documents.fiscal_document_id"),
            nullable=True,
        ),
        sa.Column("buyer_name", sa.String(150), nullable=False),
        sa.Column("buyer_tax_id", sa.String(11), nullable=False),
        sa.Column("payment_method", sa.String(20), nullable=False),
        sa.Column("subtotal", MONEY, nullable=False),
        sa.Column("itbis", MONEY, nullable=False),
        sa.Column("total", MONEY, nullable=False),
        sa.Column("void_reason", sa.String(2), nullable=True),
        sa.Column("void_note", sa.String(250), nullable=True),
        sa.Column("ecf_status", sa.String(20), nullable=True),
        sa.Column("track_id", sa.String(100), nullable=True),
        sa.Column("security_code", sa.String(20), nullable=True),
        sa.Column("signed_at", sa.DateTime(), nullable=True),
        sa.Column("qr_url", sa.String(500), nullable=True),
        users("created_by"),
        sa.UniqueConstraint("institution_id", "ncf", name="uq_fiscal_documents_ncf"),
    )
    op.create_index("ix_fiscal_documents_payment_id", "fiscal_documents", ["payment_id"])
    op.create_table(
        "fiscal_document_lines",
        sa.Column("fiscal_document_line_id", sa.Integer(), primary_key=True),
        institution("fiscal_document_lines"),
        sa.Column(
            "fiscal_document_id",
            sa.Integer(),
            sa.ForeignKey("fiscal_documents.fiscal_document_id"),
            nullable=False,
            index=True,
        ),
        sa.Column("description", sa.String(200), nullable=False),
        sa.Column("itbis_rate", RATE, nullable=False),
        sa.Column("base_amount", MONEY, nullable=False),
        sa.Column("itbis_amount", MONEY, nullable=False),
        sa.Column("line_total", MONEY, nullable=False),
    )
    with op.batch_alter_table("student_accounts") as batch:
        batch.add_column(
            sa.Column("bill_to_name", sa.String(150), nullable=False, server_default="")
        )
        batch.add_column(
            sa.Column("bill_to_tax_id", sa.String(11), nullable=False, server_default="")
        )
    for table in ("billing_concepts", "charges"):
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("itbis_rate", RATE, nullable=False, server_default="0"))
    if op.get_bind().dialect.name == "postgresql":
        for table in TABLES:
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(
                f"CREATE POLICY tenant_isolation ON {table} USING ({POLICY}) WITH CHECK ({POLICY})"
            )


def downgrade() -> None:
    for table in ("charges", "billing_concepts"):
        with op.batch_alter_table(table) as batch:
            batch.drop_column("itbis_rate")
    with op.batch_alter_table("student_accounts") as batch:
        batch.drop_column("bill_to_tax_id")
        batch.drop_column("bill_to_name")
    op.drop_table("fiscal_document_lines")
    op.drop_index("ix_fiscal_documents_payment_id", table_name="fiscal_documents")
    op.drop_table("fiscal_documents")
    op.drop_table("fiscal_sequences")
    op.drop_table("fiscal_profiles")
