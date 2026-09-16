from typing import Optional

from pydantic import BaseModel, ConfigDict


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
    model_config = ConfigDict(from_attributes=True)
