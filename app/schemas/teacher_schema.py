from pydantic import BaseModel, EmailStr
from typing import Optional

class TeacherBase(BaseModel):
    first_name:str
    last_name:str
    specialty:str
    email: EmailStr
    telephone: str
    address: str
    active: bool = True

class TeacherCreate(TeacherBase):
    pass

class TeacherUptade(BaseModel):
    first_name:Optional[str] = None
    last_name:Optional[str] = None
    specialty:Optional[str] = None
    email: Optional[EmailStr] = None
    telephone: Optional[str] = None
    address: Optional[str] = None
    active: Optional[bool] = None

class TeacherOut(TeacherBase):
    teacher_id: int
    class Config:
        from_attributes = True