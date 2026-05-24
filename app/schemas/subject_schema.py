from pydantic import BaseModel
from typing import Optional

class SubjectBase(BaseModel):
    code: str
    description: Optional[str] = None

class SubjectCreate(SubjectBase):
    pass

class SubjectUpdate(BaseModel):
    code: Optional[str] = None
    description: Optional[str] = None

class SubjectOut(SubjectBase):
    subject_id: int
    class Config:
        from_attributes = True