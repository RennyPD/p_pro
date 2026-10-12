from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.schemas.grade_schema import ReasonText

AssessmentName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)
]


class AssessmentCreate(BaseModel):
    section_id: int
    name: AssessmentName
    weight: float = Field(gt=0, le=100)
    due_date: date | None = None


class AssessmentUpdate(BaseModel):
    name: AssessmentName | None = None
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


class AssessmentTemplateCreate(BaseModel):
    name: AssessmentName
    weight: float = Field(gt=0, le=100)


class AssessmentTemplateOut(AssessmentTemplateCreate):
    assessment_template_id: int
    model_config = ConfigDict(from_attributes=True)


class AssessmentTemplateApply(BaseModel):
    section_id: int
    due_date: date | None = None


class FinalGradeOut(BaseModel):
    enrollment_id: int
    student_id: int
    student_name: str
    weighted_grade: float
    completed_weight: float
    final: bool
    status: str
    configured_weight: float = 0
    calculation_mode: str = "weighted"


class ReasonRequest(BaseModel):
    reason: ReasonText


class PlanComponent(BaseModel):
    name: AssessmentName
    weight: float = Field(gt=0, le=100)
    due_date: date | None = None


class PlanTemplateCreate(BaseModel):
    name: AssessmentName
    subject_id: int
    components: list[PlanComponent] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def validate_plan(self):
        names = [item.name.strip().casefold() for item in self.components]
        if len(set(names)) != len(names) or any(not name for name in names):
            raise ValueError("Los componentes deben tener nombres distintos")
        if abs(sum(item.weight for item in self.components) - 100) > 0.001:
            raise ValueError("La plantilla completa debe sumar 100%")
        return self


class PlanTemplateOut(BaseModel):
    assessment_template_id: int
    name: str
    subject_id: int
    components: list[PlanComponent]
    model_config = ConfigDict(from_attributes=True)


class WeightItem(BaseModel):
    assessment_id: int
    weight: float = Field(gt=0, le=100)


class DistributionUpdate(ReasonRequest):
    components: list[WeightItem] = Field(min_length=1, max_length=30)
