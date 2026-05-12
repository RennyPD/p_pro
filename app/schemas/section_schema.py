from pydantic import BaseModel, field_validator
from typing import List,Optional
from datetime import time
from app.enums.dayEnum import DayEnum

class SectionBase(BaseModel):
    code: str
    description: str
    teacher_id: int
    subject_id: int
    days_of_week:List[DayEnum]
    start_time: time
    end_time: time

class SectionCreate(SectionBase):
    pass

class SectionUpdate(BaseModel):
    code: Optional[str] = None
    description: Optional[str] = None
    teacher_id: Optional[int] = None
    subject_id: Optional[int] = None
    days_of_week: List[DayEnum] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None

class SectionOut(SectionBase):
    section_id: int

    @field_validator("days_of_week", mode="before")
    @classmethod
    def split_days(cls, v):
        if isinstance(v, str):
            return v.split(", ")
        return v

    class Config:
        from_attributes = True    