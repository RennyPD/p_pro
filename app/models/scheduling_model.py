from sqlalchemy import Boolean, ForeignKey, Integer, String, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Classroom(Base):
    __tablename__ = "classrooms"

    classroom_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    capacity: Mapped[int] = mapped_column(Integer, default=30)
    location: Mapped[str] = mapped_column(String(200), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class SectionMeeting(Base):
    __tablename__ = "section_meetings"
    __table_args__ = (
        UniqueConstraint("section_id", "day_of_week", "start_time", name="uq_section_meeting_slot"),
    )

    meeting_id: Mapped[int] = mapped_column(primary_key=True)
    section_id: Mapped[int] = mapped_column(ForeignKey("sections.section_id"))
    classroom_id: Mapped[int | None] = mapped_column(
        ForeignKey("classrooms.classroom_id"), nullable=True
    )
    day_of_week: Mapped[str] = mapped_column(String(20))
    start_time: Mapped[Time] = mapped_column(Time)
    end_time: Mapped[Time] = mapped_column(Time)
    modality: Mapped[str] = mapped_column(String(20), default="in_person")
    virtual_url: Mapped[str] = mapped_column(String(500), default="")

    section: Mapped["Section"] = relationship("Section")
    classroom: Mapped["Classroom | None"] = relationship("Classroom")
