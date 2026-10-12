from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class TeacherDossierFields(BaseModel):
    employee_code: str | None = Field(default=None, max_length=50)
    document_number: str | None = Field(default=None, max_length=50)
    birth_date: date | None = None
    nationality: str | None = Field(default=None, max_length=100)
    academic_degree: str | None = Field(default=None, max_length=150)
    alma_mater: str | None = Field(default=None, max_length=255)
    professional_license: str | None = Field(default=None, max_length=100)
    experience_years: int | None = Field(default=None, ge=0, le=80)
    department: str | None = Field(default=None, max_length=150)
    teaching_category: str | None = Field(default=None, max_length=100)
    employment_type: Literal["full_time", "part_time", "adjunct", "substitute"] | None = None
    appointment_date: date | None = None
    emergency_contact_name: str | None = Field(default=None, max_length=150)
    emergency_contact_phone: str | None = Field(default=None, max_length=30)
    emergency_contact_relationship: str | None = Field(default=None, max_length=60)


class TeacherBase(TeacherDossierFields):
    first_name: str
    last_name: str
    specialty: str
    email: EmailStr
    telephone: str
    address: str
    active: bool = True


class TeacherCreate(TeacherBase):
    pass


class TeacherUpdate(TeacherDossierFields):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    specialty: Optional[str] = None
    email: Optional[EmailStr] = None
    telephone: Optional[str] = None
    address: Optional[str] = None
    active: Optional[bool] = None


class TeacherOut(TeacherBase):
    teacher_id: int
    assigned_sections: int = 0
    model_config = ConfigDict(from_attributes=True)


class TeacherMeeting(BaseModel):
    day: str
    start_time: str
    end_time: str
    room: str
    modality: str


class TeacherSectionLoad(BaseModel):
    section_id: int
    section_code: str
    subject_code: str
    subject_name: str
    period: str
    status: str
    modality: str
    room: str
    days_of_week: list[str]
    start_time: str
    end_time: str
    capacity: int
    enrolled_students: int
    scheduled_weekly_hours: float
    meetings: list[TeacherMeeting] = Field(default_factory=list)


class TeacherWorkload(BaseModel):
    teacher_id: int
    selected_period: str | None = None
    periods: list[str]
    active_sections: int
    unique_students: int
    scheduled_weekly_hours: float
    sections: list[TeacherSectionLoad]
