from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.db.tenant import TenantMixin


class Subject(TenantMixin, Base):
    __tablename__ = "subjects"
    __table_args__ = (
        UniqueConstraint("institution_id", "code", name="uq_subjects_institution_code"),
    )

    subject_id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(255))

    sections: Mapped[list["Section"]] = relationship("Section", back_populates="subject")
