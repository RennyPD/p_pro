from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class GradeBase(BaseModel):
    enrollment_id: int
    grade_value: float = Field(ge=0, le=100)
    grade_type: str
    date_recorded: str


class GradeCreate(GradeBase):
    pass


class GradeUpdate(BaseModel):
    enrollment_id: Optional[int] = None
    grade_value: Optional[float] = Field(default=None, ge=0, le=100)
    grade_type: Optional[str] = None
    date_recorded: Optional[str] = None


class GradeOut(GradeBase):
    grade_id: int
    model_config = ConfigDict(from_attributes=True)


class GradeBulkItem(BaseModel):
    enrollment_id: int
    grade_value: float = Field(ge=0, le=100)


class GradeBulkCreate(BaseModel):
    section_id: int
    grade_type: str
    date_recorded: str
    records: list[GradeBulkItem]
