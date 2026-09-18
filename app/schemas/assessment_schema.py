from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class AssessmentCreate(BaseModel):
    section_id: int
    name: str = Field(min_length=2, max_length=100)
    weight: float = Field(gt=0, le=100)
    due_date: date | None = None


class AssessmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    weight: float | None = Field(default=None, gt=0, le=100)
    due_date: date | None = None


class AssessmentOut(BaseModel):
    assessment_id: int
    section_id: int
    name: str
    weight: float
    due_date: date | None
    closed: bool
    model_config = ConfigDict(from_attributes=True)


class FinalGradeOut(BaseModel):
    enrollment_id: int
    student_id: int
    student_name: str
    weighted_grade: float
    completed_weight: float
    final: bool
    status: str
