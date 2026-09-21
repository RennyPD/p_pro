from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class EquivalenceCreate(BaseModel):
    career_id: int
    source_subject_id: int
    target_subject_id: int
    curriculum_version: str = "current"
    notes: str = ""


class EquivalenceOut(EquivalenceCreate):
    course_equivalence_id: int
    source_code: str
    source_name: str
    target_code: str
    target_name: str


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
