from pydantic import BaseModel
from typing import Optional

class GradeBase(BaseModel):
    enrollmnent_id: int
    grade_value: float
    grade_type: str
    date_recorded: str

class GradeCreate(GradeBase):
    pass

class GradeUpdate(BaseModel):
    enrollmnent_id: Optional[int] = None
    grade_value: Optional[float] = None
    grade_type: Optional[str] = None
    date_recorded: Optional[str] = None

class GradeOut(GradeBase):
    grade_id: int

    class Config:
        from_attributes = True    