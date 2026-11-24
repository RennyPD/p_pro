from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field


class PlatformLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)
    otp: str = Field(pattern=r"^\d{6}$")


class PlatformToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    name: str
    email: str


class PlatformMe(BaseModel):
    platform_admin_id: int
    name: str
    email: str


class InstitutionCreate(BaseModel):
    name: str = Field(min_length=3, max_length=150)
    code: str = Field(min_length=3, max_length=40)
    institution_type: str = Field(pattern=r"^(university|school|both)$")
    admin_email: EmailStr
    enrollment_prefix: str = Field(
        default="EST", min_length=1, max_length=20, pattern=r"^[A-Za-z0-9-]+$"
    )
    # Fase 4 D: every new institution starts a free trial of this plan.
    plan_code: str = Field(default="profesional", min_length=2, max_length=40)


class InstitutionStatusChange(BaseModel):
    reason: str = Field(min_length=5, max_length=250)


class InstitutionUsage(BaseModel):
    students: int
    users: int
    staff: int = 0
    storage_bytes: int = 0
    last_activity: datetime | None = None


class PlanFields(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    description: str = Field(default="", max_length=300)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    monthly_price: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    yearly_price: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    max_students: int | None = Field(default=None, ge=1)
    max_staff: int | None = Field(default=None, ge=1)
    storage_gb: int | None = Field(default=None, ge=1)
    public: bool = True
    active: bool = True
    sort_order: int = 0
    provider_monthly_price: str | None = Field(default=None, max_length=120)
    provider_yearly_price: str | None = Field(default=None, max_length=120)


class PlanCreate(PlanFields):
    code: str = Field(min_length=2, max_length=40, pattern=r"^[a-z0-9-]+$")


class PlanOut(PlanCreate):
    plan_id: int


class SubscriptionOut(BaseModel):
    plan_code: str
    plan_name: str
    status: str
    interval: str
    trial_ends_at: datetime | None = None
    current_period_end: datetime | None = None
    provider: str


class SubscriptionChange(BaseModel):
    plan_code: str = Field(min_length=2, max_length=40)
    interval: str = Field(default="monthly", pattern=r"^(monthly|yearly)$")
    # Optional: extend or start a trial of N days (for example after a sales call).
    trial_days: int | None = Field(default=None, ge=1, le=365)
    reason: str = Field(min_length=5, max_length=250)


class InstitutionOut(BaseModel):
    institution_id: int
    name: str
    code: str
    status: str
    contact_email: str | None = None
    status_reason: str | None = None
    status_changed_at: datetime | None = None
    created_at: datetime
    usage: InstitutionUsage
    subscription: SubscriptionOut | None = None
    address: str | None = None


class PlatformAuditOut(BaseModel):
    platform_audit_log_id: int
    actor: str | None
    action: str
    resource: str
    detail: str
    created_at: datetime


class PublicInstitution(BaseModel):
    code: str
    name: str
    status: str
