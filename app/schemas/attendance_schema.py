from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AttendanceCreate(BaseModel):
    enrollment_id: int
    date: Optional[datetime] = None
    present: bool = False


class AttendanceUpdate(BaseModel):
    date: Optional[datetime] = None
    present: Optional[bool] = None


class AttendanceOut(BaseModel):
    attendance_id: int
    enrollment_id: int
    date: datetime
    present: bool
    model_config = ConfigDict(from_attributes=True)
