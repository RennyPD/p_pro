from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=250)]
Version = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]


class EquivalenceBase(BaseModel):
    career_id: int
    source_subject_id: int
    target_subject_id: int
    curriculum_version: Version = "current"
    notes: str = Field(default="", max_length=2000)
    active: bool = True


class EquivalenceCreate(EquivalenceBase):
    reason: Reason = "Registro de regla de equivalencia"


class EquivalenceUpdate(BaseModel):
    notes: str = Field(max_length=2000)
    active: bool
    reason: Reason


class EquivalenceOut(EquivalenceBase):
    course_equivalence_id: int
    source_code: str
    source_name: str
    target_code: str
    target_name: str
    career_name: str = ""
    career_code: str = ""
    created_by: int | None = None
    updated_by: int | None = None
    updated_at: datetime | None = None


class CareerChangeCreate(BaseModel):
    new_career_id: int
    effective_date: date
    reason: str = Field(min_length=3)


class CareerHistoryOut(BaseModel):
    student_career_history_id: int
    student_id: int
    previous_career_id: int
    previous_career_name: str
    new_career_id: int
    new_career_name: str
    effective_date: date
    reason: str
    changed_by: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class GraduationRequirement(BaseModel):
    subject_code: str
    subject_name: str
    credits: float
    course_type: str
    status: str
    recognition_type: str = "direct"
    equivalence_ids: list[int] = Field(default_factory=list)


class GraduationAudit(BaseModel):
    student_id: int
    career_name: str
    curriculum_version: str
    required_credits: float
    earned_credits: float
    remaining_credits: float
    completion_percentage: float
    eligible: bool
    requirements: list[GraduationRequirement]
