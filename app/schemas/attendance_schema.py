from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

AttendanceStatus = Literal["present", "absent", "late", "excused", "early_departure"]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=250)]


class AttendanceCreate(BaseModel):
    enrollment_id: int
    date: datetime | None = None
    present: bool | None = None
    status: AttendanceStatus | None = None
    note: str = Field(default="", max_length=300)
    excuse_reference: str = Field(default="", max_length=300)
    reason: Reason = "Registro de asistencia"
    exception_reason: Reason | None = None


class AttendanceUpdate(BaseModel):
    date: datetime | None = None
    present: bool | None = None
    status: AttendanceStatus | None = None
    note: str | None = Field(default=None, max_length=300)
    excuse_reference: str | None = Field(default=None, max_length=300)
    reason: Reason
    exception_reason: Reason | None = None


class AttendanceOut(BaseModel):
    attendance_id: int
    enrollment_id: int
    date: datetime
    present: bool
    status: str
    note: str
    excuse_reference: str
    student_name: str
    section_code: str
    subject_name: str
    model_config = ConfigDict(from_attributes=True)


class AttendanceBulkItem(BaseModel):
    enrollment_id: int
    present: bool | None = None
    status: AttendanceStatus | None = None
    note: str = Field(default="", max_length=300)
    excuse_reference: str = Field(default="", max_length=300)


class AttendanceBulkCreate(BaseModel):
    section_id: int
    date: date
    records: list[AttendanceBulkItem] = Field(min_length=1, max_length=500)
    reason: Reason = "Registro de asistencia"
    exception_reason: Reason | None = None
