from pydantic import BaseModel, EmailStr

class StudentCreate(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    enrollment_number: str
    telephone: str
    address: str
    career_id: int
    active: bool = True

class StudentUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
    enrollment_number: str | None = None
    telephone: str | None = None
    address: str | None = None
    career_id: int | None = None
    active: bool | None = None

class StudentOut(BaseModel):
    student_id: int
    first_name: str
    last_name: str
    email: EmailStr
    enrollment_number: str
    telephone: str
    address: str
    active: bool
    career_id: int

    class Config:
        from_attributes = True    