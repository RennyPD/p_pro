from sqlalchemy import ForeignKey, Float, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base

class Grade(Base):
    __tablename__ = "grades"

    grade_id: Mapped[int] = mapped_column(primary_key=True, index=True)
    enrollment_id: Mapped[int] = mapped_column(
        ForeignKey("enrollments.enrollment_id")
    )
    grade_value: Mapped[float] = mapped_column(Float)
    grade_type: Mapped[str] = mapped_column(String(50))
    date_recorded: Mapped[str] = mapped_column(String(50))

    enrollment: Mapped["Enrollment"] = relationship("Enrollment", back_populates="grades")