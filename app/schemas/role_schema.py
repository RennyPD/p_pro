from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class RoleBase(BaseModel):
    name: str
    description: str
    label: str | None = Field(default=None, min_length=1, max_length=100)


class RoleCreate(RoleBase):
    pass


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    label: str | None = Field(default=None, min_length=1, max_length=100)


class RoleOut(RoleBase):
    role_id: int
    role_title: str
    model_config = ConfigDict(from_attributes=True)
