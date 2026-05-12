from pydantic import BaseModel, EmailStr
from typing import Optional

class StudentBase(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    enrollment_number: str
    telephone: str
    address: str
    career_id: int
    active: bool = True

class StudentCreate(StudentBase):
    pass

class StudentUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: EmailStr | None = None
    enrollment_number: Optional[str] = None
    telephone: Optional[str] = None
    address: Optional[str] = None
    career_id: Optional[str] = None
    active: Optional[bool] = None

class StudentOut(StudentBase):
    student_id: int

    class Config:
        from_attributes = True    