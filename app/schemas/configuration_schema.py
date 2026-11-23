from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator

# quarter: the four periods of the MINERD school year (Fase 3 B).
PERIOD_TYPES = r"^(bimester|trimester|quarter|quadrimester|semester|annual)$"
PERIOD_LIMITS = {
    "bimester": 6,
    "trimester": 4,
    "quarter": 4,
    "quadrimester": 3,
    "semester": 2,
    "annual": 1,
}
SCHEMES = r"^(bimesters|trimesters|quarters|quadrimesters|semesters|annual)$"
SCHEME_PERIODS = {
    "bimesters": ("bimester", 6),
    "trimesters": ("trimester", 4),
    "quarters": ("quarter", 4),
    "quadrimesters": ("quadrimester", 3),
    "semesters": ("semester", 2),
    "annual": ("annual", 1),
}


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
    period_type: str = Field(default="semester", pattern=PERIOD_TYPES)
    sequence: int = Field(default=1, ge=1, le=12)
    academic_year: str = Field(default="", max_length=20)

    @model_validator(mode="after")
    def validate_dates(self):
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("El período necesita un nombre")
        if self.start_date >= self.end_date:
            raise ValueError("La fecha de fin debe ser posterior a la de inicio")
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
        if self.sequence > PERIOD_LIMITS[self.period_type]:
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
    period_type: str | None = Field(default=None, pattern=PERIOD_TYPES)
    sequence: int | None = Field(default=None, ge=1, le=12)
    academic_year: str | None = Field(default=None, max_length=20)


class AcademicPeriodOut(AcademicPeriodBase):
    period_id: int
    school_year_id: int | None = None
    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def validate_dates(self):
        # Strict chronology is enforced on writes, not retroactively on legacy reads.
        return self


class SchoolYearBase(BaseModel):
    name: str = Field(min_length=1, max_length=20)
    start_date: date
    end_date: date
    period_scheme: str = Field(default="semesters", pattern=SCHEMES)

    @model_validator(mode="after")
    def validate_year(self):
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("El año lectivo necesita un nombre")
        if self.start_date >= self.end_date:
            raise ValueError("La fecha de fin debe ser posterior a la de inicio")
        if (self.end_date - self.start_date).days > 550:
            raise ValueError("Un año lectivo no puede durar más de 18 meses")
        return self


class SchoolYearCreate(SchoolYearBase):
    # None: quarters (4, MINERD) in schools, semesters in universities.
    period_scheme: str | None = Field(default=None, pattern=SCHEMES)


class SchoolYearUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=20)
    start_date: date | None = None
    end_date: date | None = None
    period_scheme: str | None = Field(default=None, pattern=SCHEMES)


class SchoolYearOut(SchoolYearBase):
    school_year_id: int
    period_count: int = 0
    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def validate_year(self):
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
    students_view_finance: bool = True
    institution_type: str = Field(default="university", pattern=r"^(university|school|both)$")
    school_code: str = Field(default="", max_length=30)
    regional: str = Field(default="", max_length=80)
    district: str = Field(default="", max_length=80)
    school_phone: str = Field(default="", max_length=30)
    province: str = Field(default="", max_length=80)
    municipality: str = Field(default="", max_length=80)

    @model_validator(mode="after")
    def clean_name(self):
        self.institution_name = self.institution_name.strip()
        if len(self.institution_name) < 2:
            raise ValueError("El nombre institucional debe tener al menos dos caracteres")
        return self


class InstitutionSettingsUpdate(InstitutionSettingsBase):
    # Optional on update: an older client that omits it keeps the saved value.
    students_view_finance: bool | None = None
    institution_type: str | None = Field(default=None, pattern=r"^(university|school|both)$")
    school_code: str | None = Field(default=None, max_length=30)
    regional: str | None = Field(default=None, max_length=80)
    district: str | None = Field(default=None, max_length=80)
    school_phone: str | None = Field(default=None, max_length=30)
    province: str | None = Field(default=None, max_length=80)
    municipality: str | None = Field(default=None, max_length=80)
    reason: str = Field(
        default="Actualización de configuración institucional", min_length=3, max_length=250
    )
    expected_revision: int | None = Field(default=None, ge=0)


class InstitutionSettingsOut(InstitutionSettingsBase):
    revision: int = 0
    settings_id: int
    next_enrollment_number: int
    enrollment_preview: str
