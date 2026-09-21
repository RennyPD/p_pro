from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CareerBase(BaseModel):
    code: str | None = Field(default=None, min_length=2, max_length=30, pattern=r"^[A-Za-z0-9-]+$")
    name: str
    description: str
    academic_level: str = Field(
        default="undergraduate", pattern=r"^(technical|undergraduate|graduate|postgraduate)$"
    )
    degree_title: str = ""
    term_type: str = Field(
        default="semester", pattern=r"^(bimester|trimester|quadrimester|semester|annual)$"
    )
    duration_terms: int = Field(default=8, ge=1, le=20)
    required_credits: int = Field(default=120, ge=1, le=400)
    curriculum_version: str = Field(default="current", min_length=1, max_length=30)


class CareerCreate(CareerBase):
    pass


class CareerUpdate(BaseModel):
    code: Optional[str] = Field(
        default=None, min_length=2, max_length=30, pattern=r"^[A-Za-z0-9-]+$"
    )
    name: Optional[str] = None
    description: Optional[str] = None
    academic_level: Optional[str] = Field(
        default=None, pattern=r"^(technical|undergraduate|graduate|postgraduate)$"
    )
    degree_title: Optional[str] = None
    term_type: Optional[str] = Field(
        default=None, pattern=r"^(bimester|trimester|quadrimester|semester|annual)$"
    )
    duration_terms: Optional[int] = Field(default=None, ge=1, le=20)
    required_credits: Optional[int] = Field(default=None, ge=1, le=400)
    curriculum_version: Optional[str] = Field(default=None, min_length=1, max_length=30)


class CareerOut(CareerBase):
    career_id: int
    code: str
    model_config = ConfigDict(from_attributes=True)
