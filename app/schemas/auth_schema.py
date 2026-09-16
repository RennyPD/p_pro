from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from app.schemas.user_schema import UserOut


class LoginRequest(BaseModel):
    username: str
    password: str = Field(min_length=8)


class BootstrapRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    student_id: Optional[int] = None
    teacher_id: Optional[int] = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=8)
    new_password: str = Field(min_length=10)
