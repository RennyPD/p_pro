from pydantic import BaseModel
from typing import Optional

class UserBase(BaseModel):
    username: str
    email: str
    password: str
    role_id: int
    student_id: Optional[int] = None
    teacher_id: Optional[int] = None

class UserCreate(UserBase):
    pass

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    role_id: Optional[int] = None
    student_id: Optional[int] = None
    teacher_id: Optional[int] = None

class UserOut(UserBase):
    user_id: int

    class Config:
        from_attributes = True