from datetime import time

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ClassroomCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    capacity: int = Field(default=30, ge=1, le=1000)
    location: str = Field(default="", max_length=200)
    active: bool = True


class ClassroomOut(ClassroomCreate):
    classroom_id: int
    model_config = ConfigDict(from_attributes=True)


class MeetingCreate(BaseModel):
    section_id: int
    classroom_id: int | None = None
    day_of_week: str
    start_time: time
    end_time: time
    modality: str = Field(default="in_person", pattern=r"^(in_person|virtual|hybrid)$")
    virtual_url: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def validate_time(self):
        if self.start_time >= self.end_time:
            raise ValueError("end_time must be later than start_time")
        if self.modality == "virtual" and not self.virtual_url:
            raise ValueError("virtual_url is required for virtual meetings")
        return self


class MeetingOut(MeetingCreate):
    meeting_id: int
    classroom_name: str | None = None
    model_config = ConfigDict(from_attributes=True)
