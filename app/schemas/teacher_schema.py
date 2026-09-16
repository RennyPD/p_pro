from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr


class TeacherBase(BaseModel):
    first_name: str
    last_name: str
    specialty: str
    email: EmailStr
    telephone: str
    address: str
    active: bool = True


class TeacherCreate(TeacherBase):
    pass


class TeacherUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    specialty: Optional[str] = None
    email: Optional[EmailStr] = None
    telephone: Optional[str] = None
    address: Optional[str] = None
    active: Optional[bool] = None


class TeacherOut(TeacherBase):
    teacher_id: int
    model_config = ConfigDict(from_attributes=True)
