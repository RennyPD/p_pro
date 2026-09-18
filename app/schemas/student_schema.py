from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr


class StudentBase(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    enrollment_number: str | None = None
    telephone: str
    address: str
    career_id: int
    active: bool = True
    academic_hold: bool = False
    financial_hold: bool = False


class StudentCreate(StudentBase):
    pass


class StudentUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: EmailStr | None = None
    enrollment_number: Optional[str] = None
    telephone: Optional[str] = None
    address: Optional[str] = None
    career_id: Optional[int] = None
    active: Optional[bool] = None
    academic_hold: Optional[bool] = None
    financial_hold: Optional[bool] = None


class StudentOut(StudentBase):
    student_id: int
    enrollment_number: str
    model_config = ConfigDict(from_attributes=True)
