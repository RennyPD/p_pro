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


class AnnouncementBase(BaseModel):
    title: str = Field(min_length=2, max_length=150)
    body: str = Field(min_length=2, max_length=5000)
    audience: str = Field(
        default="all", pattern=r"^(all|admin|teacher|student|guardian|section|section_guardians)$"
    )
    section_id: int | None = None

    @model_validator(mode="after")
    def validate_section(self):
        self.title, self.body = self.title.strip(), self.body.strip()
        if len(self.title) < 2 or len(self.body) < 2:
            raise ValueError("Escribe un título y mensaje completos")
        if self.audience in {"section", "section_guardians"} and self.section_id is None:
            raise ValueError("section_id is required for section announcements")
        if self.audience not in {"section", "section_guardians"} and self.section_id is not None:
            raise ValueError("Solo los avisos de sección admiten section_id")
        return self


class AnnouncementCreate(AnnouncementBase):
    delivery_key: str | None = Field(default=None, min_length=8, max_length=100)
    expected_recipients: str | None = None


class AnnouncementOut(AnnouncementBase):
    announcement_id: int
    created_by: int
    published_at: datetime
    section_name: str | None = None
    author_name: str | None = None
    delivery_count: int | None = None
    read_count: int | None = None
    model_config = ConfigDict(from_attributes=True)


class NotificationOut(BaseModel):
    announcement_id: int | None = None
    notification_id: int
    user_id: int
    title: str
    body: str
    category: str
    created_at: datetime
    read_at: datetime | None
    model_config = ConfigDict(from_attributes=True)
