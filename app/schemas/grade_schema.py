from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

ReasonText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=250)]


class GradeBase(BaseModel):
    enrollment_id: int
    assessment_id: int | None = None
    grade_value: float = Field(ge=0, le=100)
    grade_type: str
    date_recorded: str


class GradeCreate(GradeBase):
    status: str = Field(default="published", pattern=r"^(draft|published)$")
    reason: ReasonText = "Registro individual"


class GradeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enrollment_id: Optional[int] = None
    assessment_id: Optional[int] = None
    grade_value: Optional[float] = Field(default=None, ge=0, le=100)
    grade_type: Optional[str] = None
    date_recorded: Optional[str] = None
    status: str | None = Field(default=None, pattern=r"^(draft|published)$")
    reason: ReasonText


class GradeOut(GradeBase):
    grade_id: int
    status: str = "published"
    model_config = ConfigDict(from_attributes=True)


class GradeBulkItem(BaseModel):
    enrollment_id: int
    grade_value: float = Field(ge=0, le=100)


class GradeBulkCreate(BaseModel):
    section_id: int
    assessment_id: int | None = None
    grade_type: str
    date_recorded: str
    records: list[GradeBulkItem]
    status: str = Field(default="draft", pattern=r"^(draft|published)$")
    reason: ReasonText = "Carga desde libro de notas"


class GradeChangeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    grade_change_id: int
    grade_id: int
    previous_value: float | None
    new_value: float
    changed_by: int
    reason: str
    changed_at: datetime
    action: str
    previous_status: str | None
    new_status: str | None
    changed_by_name: str = ""
