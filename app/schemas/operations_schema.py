from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CalendarEventCreate(BaseModel):
    title: str = Field(min_length=2, max_length=150)
    description: str = ""
    event_type: str = Field(
        default="activity", pattern=r"^(activity|exam|meeting|deadline|holiday)$"
    )
    audience: str = Field(default="all", pattern=r"^(all|admin|teacher|student|section)$")
    section_id: int | None = None
    starts_at: datetime
    ends_at: datetime
    no_school: bool = False

    @model_validator(mode="after")
    def validate_range(self):
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        if self.audience == "section" and self.section_id is None:
            raise ValueError("section_id is required for a section event")
        return self


class CalendarEventOut(CalendarEventCreate, OrmModel):
    calendar_event_id: int
    created_by: int


class LessonPlanCreate(BaseModel):
    section_id: int
    scheduled_date: date
    title: str = Field(min_length=2, max_length=150)
    content: str = Field(min_length=2)
    competencies: str = ""
    status: str = Field(default="planned", pattern=r"^(planned|delivered|cancelled)$")


class LessonPlanOut(LessonPlanCreate, OrmModel):
    lesson_plan_id: int
    teacher_id: int


class AssignmentCreate(BaseModel):
    section_id: int
    title: str = Field(min_length=2, max_length=150)
    instructions: str = Field(min_length=2)
    due_at: datetime
    max_score: float = Field(default=100, gt=0, le=1000)
    assessment_id: int | None = None
    published: bool = True


class AssignmentOut(AssignmentCreate, OrmModel):
    assignment_id: int
    created_by: int


class SubmissionCreate(BaseModel):
    content: str = Field(min_length=1, max_length=20000)


class SubmissionGrade(BaseModel):
    score: float = Field(ge=0)
    feedback: str = ""


class SubmissionOut(OrmModel):
    submission_id: int
    assignment_id: int
    student_id: int
    content: str
    submitted_at: datetime
    status: str
    score: float | None
    feedback: str


class AlertCreate(BaseModel):
    student_id: int
    category: str = Field(pattern=r"^(attendance|academic|financial|behavior|other)$")
    severity: str = Field(default="medium", pattern=r"^(low|medium|high|critical)$")
    reason: str = Field(min_length=2)


class AlertOut(AlertCreate, OrmModel):
    early_alert_id: int
    status: str
    created_by: int | None
    created_at: datetime
    resolved_at: datetime | None


class AdmissionCreate(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    telephone: str
    career_id: int
    checklist: str = ""
    notes: str = ""


class AdmissionUpdate(BaseModel):
    status: str = Field(pattern=r"^(submitted|review|accepted|rejected|enrolled)$")
    checklist: str | None = None
    notes: str | None = None


class AdmissionOut(AdmissionCreate, OrmModel):
    admission_application_id: int
    status: str
    created_at: datetime


class ApprovalCreate(BaseModel):
    request_type: str
    resource_type: str
    resource_id: int
    reason: str = Field(min_length=2)


class ApprovalResolve(BaseModel):
    status: str = Field(pattern=r"^(approved|rejected)$")
    resolution_notes: str = ""


class ApprovalOut(ApprovalCreate, OrmModel):
    approval_request_id: int
    status: str
    requested_by: int
    resolved_by: int | None
    resolution_notes: str
    created_at: datetime
    resolved_at: datetime | None


class StudentDocumentCreate(BaseModel):
    document_type: str
    filename: str
    mime_type: str = Field(pattern=r"^(application/pdf|image/png|image/jpeg)$")
    content_base64: str
    expires_on: date | None = None


class StudentDocumentOut(OrmModel):
    student_document_id: int
    student_id: int
    document_type: str
    filename: str
    mime_type: str
    expires_on: date | None
    uploaded_by: int
    uploaded_at: datetime
