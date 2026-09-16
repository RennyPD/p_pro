from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class UserBase(BaseModel):
    username: str
    email: EmailStr
    password: str = Field(min_length=8)
    role_id: int
    student_id: Optional[int] = None
    teacher_id: Optional[int] = None


class UserCreate(UserBase):
    @model_validator(mode="after")
    def validate_profile_link(self):
        if self.student_id is not None and self.teacher_id is not None:
            raise ValueError("A user cannot link to both a student and a teacher")
        return self


class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(default=None, min_length=8)
    role_id: Optional[int] = None
    student_id: Optional[int] = None
    teacher_id: Optional[int] = None


class UserOut(BaseModel):
    user_id: int
    username: str
    email: EmailStr
    role_id: int
    student_id: Optional[int] = None
    teacher_id: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)
