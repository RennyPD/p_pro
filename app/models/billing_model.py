"""SaaS plans and subscriptions (Fase 4, block D).

Global tables: the platform defines plans; each institution has one
subscription row. Institution data never lives here.
"""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    event,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Plan(Base):
    __tablename__ = "plans"

    plan_id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(300), default="")
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    monthly_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    yearly_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    # Limits: None means unlimited.
    max_students: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_staff: Mapped[int | None] = mapped_column(Integer, nullable=True)
    storage_gb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Offered at self sign-up and in the institution's plan page.
    public: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    # Price identifiers at the payment provider (Stripe price ids, ...).
    provider_monthly_price: Mapped[str | None] = mapped_column(String(120), nullable=True)
    provider_yearly_price: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Subscription(Base):
    """One per institution. Status drives access (block D3):
    trialing / active: full access; past_due: full access and a notice;
    read_only: sign-in and reading, no writes; suspended: no access;
    canceled: like suspended, kept for history."""

    __tablename__ = "subscriptions"

    subscription_id: Mapped[int] = mapped_column(primary_key=True)
    institution_id: Mapped[int] = mapped_column(
        ForeignKey("institutions.institution_id"), unique=True
    )
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.plan_id"))
    status: Mapped[str] = mapped_column(String(20), default="trialing")
    interval: Mapped[str] = mapped_column(String(10), default="monthly")  # monthly | yearly
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    past_due_since: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    read_only_since: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    provider: Mapped[str] = mapped_column(String(20), default="sandbox")
    provider_customer_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    provider_subscription_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # Time of the latest provider event applied: older events arriving late
    # never undo newer ones (webhooks are not delivered in order).
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    plan: Mapped[Plan] = relationship()


class BillingEvent(Base):
    """Provider events already processed (webhooks are retried: apply each once)."""

    __tablename__ = "billing_events"
    __table_args__ = (
        UniqueConstraint("provider", "event_id", name="uq_billing_events_provider_event"),
    )

    billing_event_id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(20))
    event_id: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(40))
    institution_id: Mapped[int | None] = mapped_column(
        ForeignKey("institutions.institution_id"), nullable=True
    )
    outcome: Mapped[str] = mapped_column(String(200), default="")
    received_at: Mapped[datetime] = mapped_column(DateTime, default=now)


# Seeds for databases built with create_all (development, tests); the
# migration 20261125_0066 inserts the same rows. Editable from the platform.
DEFAULT_PLANS = (
    # code, name, description, monthly, yearly, students, staff, storage GB, public, order
    ("basico", "Básico", "Centros pequeños", "99.00", "990.00", 300, 30, 10, True, 1),
    ("profesional", "Profesional", "Colegios y universidades medianos", "249.00", "2490.00", 1500, 150, 50, True, 2),
    ("institucional", "Institucional", "A medida, sin límites", "0.00", "0.00", None, None, None, False, 3),
)  # fmt: skip


@event.listens_for(Plan.__table__, "after_create")
def _seed_plans(target, connection, **_kwargs) -> None:
    connection.execute(
        target.insert(),
        [
            {
                "code": code,
                "name": name,
                "description": description,
                "currency": "USD",
                "monthly_price": Decimal(monthly),
                "yearly_price": Decimal(yearly),
                "max_students": students,
                "max_staff": staff,
                "storage_gb": storage,
                "public": public,
                "active": True,
                "sort_order": order,
                "created_at": now(),
            }
            for code, name, description, monthly, yearly, students, staff, storage, public, order in DEFAULT_PLANS
        ],
    )


@event.listens_for(Subscription.__table__, "after_create")
def _first_subscription(target, connection, **_kwargs) -> None:
    connection.execute(
        text(
            "INSERT INTO subscriptions (institution_id, plan_id, status, interval, provider, updated_at) "
            "SELECT 1, plan_id, 'active', 'yearly', 'manual', CURRENT_TIMESTAMP "
            "FROM plans WHERE code = 'institucional'"
        )
    )
