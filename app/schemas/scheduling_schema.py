from datetime import time
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.enums.dayEnum import canonical_day


class ClassroomCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    capacity: int = Field(default=30, ge=1, le=1000)
    location: str = Field(default="", max_length=200)
    active: bool = True


class ClassroomOut(ClassroomCreate):
    classroom_id: int
    model_config = ConfigDict(from_attributes=True)


class ClassroomAvailability(ClassroomOut):
    """A classroom and whether it can host a section at a given time."""

    status: str  # available | busy | small | retired
    detail: str = ""


class MeetingCreate(BaseModel):
    section_id: int
    classroom_id: int | None = None
    day_of_week: str
    start_time: time
    end_time: time
    modality: str = Field(default="in_person", pattern=r"^(in_person|virtual|hybrid)$")
    virtual_url: str = Field(default="", max_length=500)

    @field_validator("day_of_week")
    @classmethod
    def validate_day(cls, value):
        if day := canonical_day(value):
            return day
        raise ValueError("Selecciona un día de lunes a domingo")

    @model_validator(mode="after")
    def validate_time(self):
        if self.start_time.tzinfo is not None or self.end_time.tzinfo is not None:
            raise ValueError("Usa horas de clase locales sin desfase horario")
        if self.start_time >= self.end_time:
            raise ValueError("La hora de fin debe ser posterior a la de inicio")
        if self.modality == "virtual" and not self.virtual_url:
            raise ValueError("Indica el enlace de la reunión virtual")
        if self.virtual_url:
            url = urlsplit(self.virtual_url)
            if url.scheme not in {"http", "https"} or not url.hostname or url.username:
                raise ValueError("Escribe un enlace HTTP o HTTPS válido para el bloque")
        return self


class MeetingOut(MeetingCreate):
    meeting_id: int
    classroom_name: str | None = None
    model_config = ConfigDict(from_attributes=True)


class ScheduleBlock(BaseModel):
    day_of_week: str
    start_time: time
    end_time: time
    room: str
    modality: str
    virtual_url: str = ""
    classroom_id: int | None = None
