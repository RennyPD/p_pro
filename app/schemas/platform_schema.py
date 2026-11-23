from datetime import datetime

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


class InstitutionStatusChange(BaseModel):
    reason: str = Field(min_length=5, max_length=250)


class InstitutionUsage(BaseModel):
    students: int
    users: int
    last_activity: datetime | None = None


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
