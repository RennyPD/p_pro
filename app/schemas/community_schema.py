from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class GuardianCreate(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    telephone: str
    address: str = ""


class GuardianLinkCreate(BaseModel):
    student_id: int
    guardian_id: int
    relationship: str
    primary_contact: bool = False
    emergency_contact: bool = False
    authorized_pickup: bool = False


class GuardianLinkOut(GuardianLinkCreate):
    student_guardian_id: int
    guardian_name: str
    guardian_email: EmailStr


class AnnouncementCreate(BaseModel):
    title: str = Field(min_length=2, max_length=150)
    body: str = Field(min_length=2, max_length=5000)
    audience: str = Field(default="all", pattern=r"^(all|admin|teacher|student|section)$")
    section_id: int | None = None

    @model_validator(mode="after")
    def validate_section(self):
        if self.audience == "section" and self.section_id is None:
            raise ValueError("section_id is required for section announcements")
        return self


class AnnouncementOut(AnnouncementCreate):
    announcement_id: int
    created_by: int
    published_at: datetime
    model_config = ConfigDict(from_attributes=True)


class NotificationOut(BaseModel):
    notification_id: int
    user_id: int
    title: str
    body: str
    category: str
    created_at: datetime
    read_at: datetime | None
    model_config = ConfigDict(from_attributes=True)
