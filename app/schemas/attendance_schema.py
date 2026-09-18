from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AttendanceCreate(BaseModel):
    enrollment_id: int
    date: Optional[datetime] = None
    present: bool = False
    status: str | None = None
    note: str = ""
    excuse_reference: str = ""


class AttendanceUpdate(BaseModel):
    date: Optional[datetime] = None
    present: Optional[bool] = None
    status: str | None = None
    note: str | None = None
    excuse_reference: str | None = None


class AttendanceOut(BaseModel):
    attendance_id: int
    enrollment_id: int
    date: datetime
    present: bool
    status: str
    note: str
    excuse_reference: str
    model_config = ConfigDict(from_attributes=True)


class AttendanceBulkItem(BaseModel):
    enrollment_id: int
    present: bool
    status: str | None = None
    note: str = ""


class AttendanceBulkCreate(BaseModel):
    section_id: int
    date: date
    records: list[AttendanceBulkItem]
