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
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("El período necesita un nombre")
        if self.start_date >= self.end_date:
            raise ValueError("end_date must be later than start_date")
        if (
            self.registration_start
            and self.registration_end
            and self.registration_start > self.registration_end
        ):
            raise ValueError("El inicio de selección no puede superar su cierre")
        if self.registration_end and self.registration_end > self.end_date:
            raise ValueError("La selección debe cerrar antes de finalizar el período")
        if (
            self.withdrawal_deadline
            and not self.start_date <= self.withdrawal_deadline <= self.end_date
        ):
            raise ValueError("El retiro debe estar dentro del período")
        if self.grading_deadline and self.grading_deadline < self.end_date:
            raise ValueError("El plazo de calificación no puede preceder al fin del período")
        if self.status == "closed" and self.active:
            raise ValueError("Un período cerrado no puede estar vigente")
        limits = {"bimester": 6, "trimester": 4, "quadrimester": 3, "semester": 2, "annual": 1}
        if self.sequence > limits[self.period_type]:
            raise ValueError("El número dentro del año no corresponde al tipo de período")
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

    @model_validator(mode="after")
    def validate_dates(self):
        # Strict chronology is enforced on writes, not retroactively on legacy reads.
        return self


class OperationReason(BaseModel):
    reason: str = Field(min_length=3, max_length=250)

    @model_validator(mode="after")
    def clean_reason(self):
        self.reason = self.reason.strip()
        if len(self.reason) < 3:
            raise ValueError("Explica el motivo de la operación")
        return self


class InstitutionSettingsBase(BaseModel):
    institution_name: str = Field(min_length=2, max_length=150)
    enrollment_prefix: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9-]+$")
    enrollment_digits: int = Field(ge=3, le=10)
    passing_grade: float = Field(ge=0, le=100)
    max_credits_per_period: int = Field(default=24, ge=1, le=60)

    @model_validator(mode="after")
    def clean_name(self):
        self.institution_name = self.institution_name.strip()
        if len(self.institution_name) < 2:
            raise ValueError("El nombre institucional debe tener al menos dos caracteres")
        return self


class InstitutionSettingsUpdate(InstitutionSettingsBase):
    reason: str = Field(
        default="Actualización de configuración institucional", min_length=3, max_length=250
    )
    expected_revision: int | None = Field(default=None, ge=0)


class InstitutionSettingsOut(InstitutionSettingsBase):
    revision: int = 0
    settings_id: int
    next_enrollment_number: int
    enrollment_preview: str
