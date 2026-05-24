from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class AttendanceBase(BaseModel):
    enrollment_id: int
    date: datetime
    present: bool

class AttendanceCreate(AttendanceBase):
    pass

class AttendanceUpdate(BaseModel):
    enrollment_id: Optional[int]
    date: Optional[datetime]
    present: Optional[bool]

class AttendanceOut(AttendanceBase):
    attendance_id: int

    class Config:
        from_attributes: True