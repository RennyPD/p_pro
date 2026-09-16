from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class EnrollmentBase(BaseModel):
    student_id: int
    section_id: int
    enrollment_date: Optional[datetime] = None
    state: Optional[str] = "enrolled"
    period: str


class EnrollmentCreate(EnrollmentBase):
    pass


class EnrollmentUpdate(BaseModel):
    student_id: Optional[int] = None
    section_id: Optional[int] = None
    enrollment_date: Optional[datetime] = None
    state: Optional[str] = None
    period: Optional[str] = None


class EnrollmentOut(EnrollmentBase):
    enrollment_id: int
    model_config = ConfigDict(from_attributes=True)
