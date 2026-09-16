from typing import Optional

from pydantic import BaseModel, ConfigDict


class SubjectBase(BaseModel):
    code: str
    description: str


class SubjectCreate(SubjectBase):
    pass


class SubjectUpdate(BaseModel):
    code: Optional[str] = None
    description: Optional[str] = None


class SubjectOut(SubjectBase):
    subject_id: int
    model_config = ConfigDict(from_attributes=True)
