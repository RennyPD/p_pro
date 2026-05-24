from pydantic import BaseModel
from typing import Optional

class CareerBase(BaseModel):
    name: str
    description: str

class CareerCreate(CareerBase):
    pass

class CareerUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class CareerOut(CareerBase):
    career_id: int

    class config:
        from_attributes = True