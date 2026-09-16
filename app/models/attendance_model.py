from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Attendance(Base):
    __tablename__ = "attendances"

    attendance_id: Mapped[int] = mapped_column(primary_key=True, index=True)
    enrollment_id: Mapped[int] = mapped_column(ForeignKey("enrollments.enrollment_id"))
    date: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )
    present: Mapped[bool] = mapped_column(Boolean, default=False)

    enrollment: Mapped["Enrollment"] = relationship("Enrollment", back_populates="attendances")
