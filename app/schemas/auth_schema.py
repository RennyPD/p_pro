from pydantic import BaseModel, EmailStr, Field

from app.schemas.user_schema import UserOut


class LoginRequest(BaseModel):
    username: str
    password: str = Field(min_length=8)
    otp: str | None = Field(default=None, pattern=r"^\d{6}$")
    # Institution code (slug); needed only when the username exists in several.
    institution: str | None = Field(default=None, max_length=60)


class BootstrapRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=8)
    new_password: str = Field(min_length=10)


class MfaCodeRequest(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


class MfaEnableRequest(MfaCodeRequest):
    current_code: str | None = Field(default=None, pattern=r"^\d{6}$")
    current_password: str = Field(min_length=8)


class MfaDisableRequest(MfaCodeRequest):
    current_password: str = Field(min_length=8)


class PasswordResetRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=255)
    institution: str | None = Field(default=None, max_length=60)


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: str = Field(min_length=10)
