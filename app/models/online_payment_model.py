"""Online card payments of families and students (Fase 4, block E).

Each institution uses its own merchant account (Azul, CardNet): the money goes
straight to the institution and card data never reaches Nexo (hosted payment
page). Nexo keeps the intent, verifies the signed answer and posts the payment.
"""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.db.tenant import TenantMixin
from app.models.finance_model import MONEY


def now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class OnlinePayment(TenantMixin, Base):
    """created -> pending (sent to the gateway) -> approved | declined | expired | error."""

    __tablename__ = "online_payments"

    online_payment_id: Mapped[int] = mapped_column(primary_key=True)
    # Order number sent to the gateway; unique everywhere (uuid hex).
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    payer_user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    gateway: Mapped[str] = mapped_column(String(20))
    amount: Mapped[Decimal] = mapped_column(MONEY)
    currency: Mapped[str] = mapped_column(String(3), default="DOP")
    status: Mapped[str] = mapped_column(String(20), default="created", index=True)
    # [{"student_id": 1, "amount_cents": 150000}, ...] (one entry per child).
    allocations: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    provider_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    authorization_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    response_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    response_message: Mapped[str | None] = mapped_column(String(250), nullable=True)
    # Comma-separated payment ids posted when approved.
    payment_ids: Mapped[str] = mapped_column(String(200), default="")
    # Approved for more than the balance at that moment: a credit to settle.
    overpaid: Mapped[bool] = mapped_column(Boolean, default=False)


class PaymentGatewayConfig(TenantMixin, Base):
    """The institution's own merchant account; secrets are stored encrypted."""

    __tablename__ = "payment_gateway_configs"
    __table_args__ = (
        UniqueConstraint("institution_id", name="uq_payment_gateway_configs_institution"),
    )

    payment_gateway_config_id: Mapped[int] = mapped_column(primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    gateway: Mapped[str] = mapped_column(String(20), default="sandbox")  # sandbox|azul|cardnet
    merchant_id: Mapped[str] = mapped_column(String(60), default="")
    merchant_name: Mapped[str] = mapped_column(String(100), default="")
    # Fernet token of a JSON object (auth keys); never sent to the browser.
    secrets: Mapped[str] = mapped_column(Text, default="")
    min_amount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("100.00"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"), nullable=True)
