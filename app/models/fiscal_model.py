"""Fiscal receipts of the Dominican Republic (Fase 4, block F).

Each institution issues with its own RNC and the sequences the DGII
authorized to it: NCF (B01, B02, B14, B15, B04) or electronic e-CF (E31,
E32, E34, E44, E45) through an authorized provider. Documents are immutable:
a reversal issues a credit note; unused numbers are voided with a reason.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.db.tenant import TenantMixin
from app.models.finance_model import MONEY

RATE = Numeric(5, 2)


def now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class FiscalProfile(TenantMixin, Base):
    """The issuer: one per institution."""

    __tablename__ = "fiscal_profiles"
    __table_args__ = (UniqueConstraint("institution_id", name="uq_fiscal_profiles_institution"),)

    fiscal_profile_id: Mapped[int] = mapped_column(primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mode: Mapped[str] = mapped_column(String(10), default="ncf")  # ncf | ecf
    rnc: Mapped[str] = mapped_column(String(11), default="")
    legal_name: Mapped[str] = mapped_column(String(150), default="")
    trade_name: Mapped[str] = mapped_column(String(150), default="")
    fiscal_address: Mapped[str] = mapped_column(String(250), default="")
    # "payment": a receipt for every posted payment; "request": on demand.
    issue_on: Mapped[str] = mapped_column(String(10), default="payment")
    ecf_provider: Mapped[str] = mapped_column(String(30), default="sandbox")
    ecf_secrets: Mapped[str] = mapped_column(Text, default="")  # encrypted (Fernet)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"), nullable=True)


class FiscalSequence(TenantMixin, Base):
    """A range the DGII authorized: B0200000001 … B0200001000, valid until a date."""

    __tablename__ = "fiscal_sequences"
    __table_args__ = (
        UniqueConstraint(
            "institution_id", "doc_type", "range_start", name="uq_fiscal_sequences_range"
        ),
    )

    fiscal_sequence_id: Mapped[int] = mapped_column(primary_key=True)
    doc_type: Mapped[str] = mapped_column(String(3))  # B01, B02, ..., E31, E32, ...
    range_start: Mapped[int] = mapped_column(Integer)
    range_end: Mapped[int] = mapped_column(Integer)
    next_number: Mapped[int] = mapped_column(Integer)
    expires_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"), nullable=True)


class FiscalDocument(TenantMixin, Base):
    __tablename__ = "fiscal_documents"
    __table_args__ = (UniqueConstraint("institution_id", "ncf", name="uq_fiscal_documents_ncf"),)

    fiscal_document_id: Mapped[int] = mapped_column(primary_key=True)
    doc_type: Mapped[str] = mapped_column(String(3))
    ncf: Mapped[str] = mapped_column(String(19))
    fiscal_sequence_id: Mapped[int | None] = mapped_column(
        ForeignKey("fiscal_sequences.fiscal_sequence_id"), nullable=True
    )
    sequence_expires_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="issued")  # issued | voided
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    student_id: Mapped[int | None] = mapped_column(ForeignKey("students.student_id"), nullable=True)
    payment_id: Mapped[int | None] = mapped_column(
        ForeignKey("payments.payment_id"), nullable=True, index=True
    )
    # Credit notes: the document they modify.
    affected_document_id: Mapped[int | None] = mapped_column(
        ForeignKey("fiscal_documents.fiscal_document_id"), nullable=True
    )
    buyer_name: Mapped[str] = mapped_column(String(150), default="")
    buyer_tax_id: Mapped[str] = mapped_column(String(11), default="")
    payment_method: Mapped[str] = mapped_column(String(20), default="cash")
    subtotal: Mapped[Decimal] = mapped_column(MONEY)
    itbis: Mapped[Decimal] = mapped_column(MONEY)
    total: Mapped[Decimal] = mapped_column(MONEY)
    void_reason: Mapped[str | None] = mapped_column(String(2), nullable=True)  # DGII 608 code
    void_note: Mapped[str | None] = mapped_column(String(250), nullable=True)
    # e-CF (block F5): provider answer.
    ecf_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    track_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    security_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    qr_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"), nullable=True)

    lines: Mapped[list["FiscalDocumentLine"]] = relationship(
        order_by="FiscalDocumentLine.fiscal_document_line_id", cascade="all, delete-orphan"
    )


class FiscalDocumentLine(TenantMixin, Base):
    __tablename__ = "fiscal_document_lines"

    fiscal_document_line_id: Mapped[int] = mapped_column(primary_key=True)
    fiscal_document_id: Mapped[int] = mapped_column(
        ForeignKey("fiscal_documents.fiscal_document_id"), index=True
    )
    description: Mapped[str] = mapped_column(String(200))
    itbis_rate: Mapped[Decimal] = mapped_column(RATE, default=Decimal("0"))
    base_amount: Mapped[Decimal] = mapped_column(MONEY)
    itbis_amount: Mapped[Decimal] = mapped_column(MONEY)
    line_total: Mapped[Decimal] = mapped_column(MONEY)
