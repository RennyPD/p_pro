from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class CareerInstitutionalFields(BaseModel):
    faculty: str | None = Field(default=None, max_length=150)
    department: str | None = Field(default=None, max_length=150)
    coordinator_name: str | None = Field(default=None, max_length=150)
    contact_email: EmailStr | None = Field(default=None, max_length=255)
    campus: str | None = Field(default=None, max_length=150)
    authorization_reference: str | None = Field(default=None, max_length=150)
    admission_profile: str | None = Field(default=None, max_length=4000)
    graduate_profile: str | None = Field(default=None, max_length=4000)
    professional_fields: str | None = Field(default=None, max_length=4000)
    admission_requirements: str | None = Field(default=None, max_length=4000)
    graduation_requirements: str | None = Field(default=None, max_length=4000)


class CareerBase(CareerInstitutionalFields):
    status: str = Field(default="active", pattern=r"^(draft|active|suspended|archived)$")
    modality: str = Field(default="in_person", pattern=r"^(in_person|virtual|hybrid)$")
    code: str | None = Field(default=None, min_length=2, max_length=30, pattern=r"^[A-Za-z0-9-]+$")
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(min_length=1, max_length=255)
    academic_level: str = Field(
        default="undergraduate", pattern=r"^(technical|undergraduate|graduate|postgraduate)$"
    )
    degree_title: str = Field(default="", max_length=150)
    term_type: str = Field(
        default="semester", pattern=r"^(bimester|trimester|quadrimester|semester|annual)$"
    )
    duration_terms: int = Field(default=8, ge=1, le=20)
    required_credits: int = Field(default=120, ge=1, le=400)
    curriculum_version: str = Field(default="current", min_length=1, max_length=30)


class CareerCreate(CareerBase):
    pass


class CareerUpdate(CareerInstitutionalFields):
    status: str | None = Field(default=None, pattern=r"^(draft|active|suspended|archived)$")
    modality: str | None = Field(default=None, pattern=r"^(in_person|virtual|hybrid)$")
    code: Optional[str] = Field(
        default=None, min_length=2, max_length=30, pattern=r"^[A-Za-z0-9-]+$"
    )
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    description: Optional[str] = Field(default=None, min_length=1, max_length=255)
    academic_level: Optional[str] = Field(
        default=None, pattern=r"^(technical|undergraduate|graduate|postgraduate)$"
    )
    degree_title: Optional[str] = Field(default=None, max_length=150)
    term_type: Optional[str] = Field(
        default=None, pattern=r"^(bimester|trimester|quadrimester|semester|annual)$"
    )
    duration_terms: Optional[int] = Field(default=None, ge=1, le=20)
    required_credits: Optional[int] = Field(default=None, ge=1, le=400)
    curriculum_version: Optional[str] = Field(default=None, min_length=1, max_length=30)

    @model_validator(mode="before")
    @classmethod
    def reject_null_catalog_state(cls, values):
        for field in ("status", "modality"):
            if field in values and values[field] is None:
                raise ValueError(f"{field} cannot be null")
        return values


class CareerOut(CareerBase):
    career_id: int
    code: str
    model_config = ConfigDict(from_attributes=True)
