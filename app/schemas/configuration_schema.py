from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AcademicPeriodBase(BaseModel):
    name: str
    start_date: date
    end_date: date
    active: bool = False
    status: str = Field(default="planning", pattern=r"^(planning|registration|active|closed)$")
    registration_start: date | None = None
    registration_end: date | None = None
    withdrawal_deadline: date | None = None
    grading_deadline: date | None = None
    period_type: str = Field(
        default="semester", pattern=r"^(bimester|trimester|quadrimester|semester|annual)$"
    )
    sequence: int = Field(default=1, ge=1, le=12)
    academic_year: str = Field(default="", max_length=20)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.start_date >= self.end_date:
            raise ValueError("end_date must be later than start_date")
        return self


class AcademicPeriodCreate(AcademicPeriodBase):
    pass


class AcademicPeriodUpdate(BaseModel):
    name: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    active: bool | None = None
    status: str | None = Field(default=None, pattern=r"^(planning|registration|active|closed)$")
    registration_start: date | None = None
    registration_end: date | None = None
    withdrawal_deadline: date | None = None
    grading_deadline: date | None = None
    period_type: str | None = Field(
        default=None, pattern=r"^(bimester|trimester|quadrimester|semester|annual)$"
    )
    sequence: int | None = Field(default=None, ge=1, le=12)
    academic_year: str | None = Field(default=None, max_length=20)


class AcademicPeriodOut(AcademicPeriodBase):
    period_id: int
    model_config = ConfigDict(from_attributes=True)


class InstitutionSettingsUpdate(BaseModel):
    institution_name: str = Field(min_length=2, max_length=150)
    enrollment_prefix: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9-]+$")
    enrollment_digits: int = Field(ge=3, le=10)
    passing_grade: float = Field(ge=0, le=100)
    max_credits_per_period: int = Field(default=24, ge=1, le=60)


class InstitutionSettingsOut(InstitutionSettingsUpdate):
    settings_id: int
    next_enrollment_number: int
    enrollment_preview: str
