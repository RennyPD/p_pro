from pydantic import BaseModel
from typing import Optional

class SubjectBase(BaseModel):
    name: str
    code: str
    description: Optional[str] = None

class SubjectCreate(SubjectBase):
    pass

class SubjectUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None

class SubjectOut(SubjectBase):
    subject_id: int
    class Config:
        from_attributes = True