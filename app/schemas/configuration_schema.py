from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AcademicPeriodBase(BaseModel):
    name: str
    start_date: date
    end_date: date
    active: bool = False

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


class AcademicPeriodOut(AcademicPeriodBase):
    period_id: int
    model_config = ConfigDict(from_attributes=True)


class InstitutionSettingsUpdate(BaseModel):
    institution_name: str = Field(min_length=2, max_length=150)
    enrollment_prefix: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9-]+$")
    enrollment_digits: int = Field(ge=3, le=10)
    passing_grade: float = Field(ge=0, le=100)


class InstitutionSettingsOut(InstitutionSettingsUpdate):
    settings_id: int
    next_enrollment_number: int
    enrollment_preview: str
