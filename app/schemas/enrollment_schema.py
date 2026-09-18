from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


class EnrollmentBase(BaseModel):
    student_id: int
    section_id: int
    enrollment_date: Optional[datetime] = None
    state: Literal["enrolled", "waitlisted", "withdrawn", "completed", "failed"] = "enrolled"
    period: str
    waitlist_position: int | None = None


class EnrollmentCreate(EnrollmentBase):
    pass


class EnrollmentUpdate(BaseModel):
    student_id: Optional[int] = None
    section_id: Optional[int] = None
    enrollment_date: Optional[datetime] = None
    state: Literal["enrolled", "waitlisted", "withdrawn", "completed", "failed"] | None = None
    period: Optional[str] = None
    waitlist_position: int | None = None


class EnrollmentOut(EnrollmentBase):
    enrollment_id: int
    model_config = ConfigDict(from_attributes=True)
