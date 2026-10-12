from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.curriculum_schema import CurriculumCourseOut
from app.schemas.section_schema import SectionOut


class SubjectBase(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=255)

    @field_validator("code", "description", mode="before")
    @classmethod
    def trim_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class SubjectCreate(SubjectBase):
    pass


class SubjectUpdate(BaseModel):
    code: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, min_length=1, max_length=255)

    @field_validator("code", "description", mode="before")
    @classmethod
    def validate_text(cls, value):
        if value is None:
            raise ValueError("Subject fields cannot be null")
        return value.strip() if isinstance(value, str) else value


class SubjectOut(SubjectBase):
    subject_id: int
    model_config = ConfigDict(from_attributes=True)


class SubjectProgramOut(CurriculumCourseOut):
    career_name: str
    career_code: str
    term_type: str
    is_current_version: bool


class SubjectOverview(BaseModel):
    subject: SubjectOut
    programs: list[SubjectProgramOut]
    sections: list[SectionOut]
