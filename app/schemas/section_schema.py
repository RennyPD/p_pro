from datetime import time
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.enums.dayEnum import DayEnum


class SectionBase(BaseModel):
    code: str
    description: str
    teacher_id: int
    subject_id: int
    days_of_week: List[DayEnum]
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def validate_time_range(self):
        if self.start_time >= self.end_time:
            raise ValueError("end_time must be later than start_time")
        return self


class SectionCreate(SectionBase):
    pass


class SectionUpdate(BaseModel):
    code: Optional[str] = None
    description: Optional[str] = None
    teacher_id: Optional[int] = None
    subject_id: Optional[int] = None
    days_of_week: Optional[List[DayEnum]] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None

    @model_validator(mode="after")
    def validate_time_range(self):
        if (
            self.start_time is not None
            and self.end_time is not None
            and self.start_time >= self.end_time
        ):
            raise ValueError("end_time must be later than start_time")
        return self


class SectionOut(SectionBase):
    section_id: int

    @field_validator("days_of_week", mode="before")
    @classmethod
    def split_days(cls, v):
        if isinstance(v, str):
            return v.split(", ")
        return v

    model_config = ConfigDict(from_attributes=True)
