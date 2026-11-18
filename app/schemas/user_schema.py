from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class UserBase(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8)
    role_id: int
    student_id: Optional[int] = None
    teacher_id: Optional[int] = None
    guardian_id: Optional[int] = None


class UserCreate(UserBase):
    @model_validator(mode="after")
    def validate_profile_link(self):
        links = [self.student_id, self.teacher_id, self.guardian_id]
        if sum(item is not None for item in links) > 1:
            raise ValueError("Una cuenta solo puede vincularse a una persona")
        return self


class UserUpdate(BaseModel):
    username: Optional[str] = Field(default=None, min_length=1, max_length=50)
    email: Optional[EmailStr] = Field(default=None, max_length=255)
    password: Optional[str] = Field(default=None, min_length=8)
    role_id: Optional[int] = None
    student_id: Optional[int] = None
    teacher_id: Optional[int] = None
    guardian_id: Optional[int] = None

    @field_validator("username", "email", "password", "role_id")
    @classmethod
    def non_nullable_fields(cls, value):
        if value is None:
            raise ValueError("Omite este campo si deseas conservar su valor")
        return value


class UserOut(BaseModel):
    user_id: int
    username: str
    email: EmailStr
    role_id: int
    student_id: Optional[int] = None
    teacher_id: Optional[int] = None
    guardian_id: Optional[int] = None
    role_name: str
    role_label: str | None = None
    linked_person: str | None = None
    mfa_enabled: bool = False
    active: bool = True
    model_config = ConfigDict(from_attributes=True)


class UserPasswordReset(BaseModel):
    password: str = Field(min_length=10)
