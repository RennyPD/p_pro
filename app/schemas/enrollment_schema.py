from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class EnrollmentBase(BaseModel):
    student_id: int
    section_id: int
    enrollment_date: Optional[datetime] = None
    state: Optional[str] = "enrolled"
    period: Optional[str] = None

class EnrollmentCreate(EnrollmentBase):
    pass

class EnrollmentUpdate(BaseModel):
    enrollment_id: Optional[int] = None
    student_id: Optional[int] = None
    section_id: Optional[int] = None
    enrollment_date: Optional[datetime] = None
    state: Optional[str] = None
    period: Optional[str] = None

class EnrollmentOut(EnrollmentBase):
    enrollment_id: int

    class Config:
        from_attributes = True