from datetime import UTC, date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CalendarEventCreate(BaseModel):
    title: str = Field(min_length=2, max_length=150)
    description: str = ""
    event_type: str = Field(
        default="activity", pattern=r"^(activity|exam|meeting|deadline|holiday)$"
    )
    audience: str = Field(default="all", pattern=r"^(all|admin|teacher|student|guardian|section)$")
    section_id: int | None = None
    starts_at: datetime
    ends_at: datetime
    no_school: bool = False

    @model_validator(mode="after")
    def validate_range(self):
        self.title = self.title.strip()
        if len(self.title) < 2:
            raise ValueError("Escribe un título para el evento")
        self.starts_at = (
            self.starts_at.astimezone(UTC).replace(tzinfo=None)
            if self.starts_at.tzinfo
            else self.starts_at
        )
        self.ends_at = (
            self.ends_at.astimezone(UTC).replace(tzinfo=None)
            if self.ends_at.tzinfo
            else self.ends_at
        )
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
    lifecycle: str = Field(default="open", pattern=r"^(open|closed|archived)$")
    allow_late: bool = False
    allow_resubmit: bool = True

    @model_validator(mode="after")
    def clean_assignment(self):
        self.title = self.title.strip()
        self.instructions = self.instructions.strip()
        if len(self.title) < 2 or len(self.instructions) < 2:
            raise ValueError("Escribe un título e instrucciones completos")
        return self


class AssignmentOut(AssignmentCreate, OrmModel):
    assignment_id: int
    created_by: int


class SubmissionCreate(BaseModel):
    content: str = Field(min_length=1, max_length=20000)

    @model_validator(mode="after")
    def clean_content(self):
        self.content = self.content.strip()
        if not self.content:
            raise ValueError("La entrega no puede estar vacía")
        return self


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
    student_name: str = ""
    enrollment_number: str = ""
    early_alert_id: int
    status: str
    created_by: int | None
    assigned_to: int | None = None
    follow_up_date: date | None = None
    resolution_notes: str = ""
    created_at: datetime
    resolved_at: datetime | None


class AlertAssignment(BaseModel):
    assigned_to: int | None = None
    follow_up_date: date | None = None


class AlertResolve(BaseModel):
    resolution_notes: str = Field(min_length=3, max_length=5000)


class AlertInterventionCreate(BaseModel):
    action_type: str = Field(pattern=r"^(contact|meeting|referral|agreement|note)$")
    notes: str = Field(min_length=2, max_length=5000)


class AlertInterventionOut(AlertInterventionCreate, OrmModel):
    performer_name: str = ""
    alert_intervention_id: int
    early_alert_id: int
    performed_by: int
    created_at: datetime


class AdmissionCreate(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    telephone: str
    career_id: int
    checklist: str = ""
    notes: str = ""


class AdmissionUpdate(BaseModel):
    expected_status: str | None = None
    reason: str = Field(
        default="Actualización del proceso de admisión", min_length=3, max_length=250
    )
    status: str = Field(pattern=r"^(submitted|review|accepted|rejected|enrolled)$")
    checklist: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def clean_reason(self):
        self.reason = self.reason.strip()
        if len(self.reason) < 3:
            raise ValueError("Explica el motivo de la transición")
        return self


class AdmissionOut(AdmissionCreate, OrmModel):
    student_id: int | None = None
    career_name: str = ""
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
