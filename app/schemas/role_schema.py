from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class RoleBase(BaseModel):
    name: str
    description: str
    label: str | None = Field(default=None, min_length=1, max_length=100)
    scope: str = Field(default="institution", pattern=r"^(institution|sections|own|linked)$")


class RoleCreate(RoleBase):
    pass


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    label: str | None = Field(default=None, min_length=1, max_length=100)
    scope: str | None = Field(default=None, pattern=r"^(institution|sections|own|linked)$")


class RoleOut(RoleBase):
    role_id: int
    role_title: str
    user_count: int = 0
    permission_count: int = 0
    model_config = ConfigDict(from_attributes=True)
