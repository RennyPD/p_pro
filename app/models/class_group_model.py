"""Fixed class groups of a school year ("1.º A") and their members (Fase 3, block C).

The grade is the term number of a school program whose term type is annual:
1.º de Secundaria is term 1 of the Secundaria program, and its subjects are
the curriculum courses of that term. A group's subjects become regular
sections, one per period of the year, so grades, attendance, period closing,
teacher scope and the guardian portal keep working unchanged.
"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

MEMBER_STATUSES = ("enrolled", "withdrawn", "transferred")
RESULTS = ("pending", "promoted", "completivo", "repeated")


class ClassGroup(Base):
    __tablename__ = "class_groups"
    __table_args__ = (
        # Careers belong to one institution, so this stays unique per institution.
        UniqueConstraint(
            "career_id", "grade_number", "name", "school_year_id", name="uq_class_group_identity"
        ),
    )

    class_group_id: Mapped[int] = mapped_column(primary_key=True)
    career_id: Mapped[int] = mapped_column(ForeignKey("careers.career_id"), index=True)
    grade_number: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(20))
    school_year_id: Mapped[int] = mapped_column(
        ForeignKey("school_years.school_year_id"), index=True
    )
    homeroom_teacher_id: Mapped[int | None] = mapped_column(
        ForeignKey("teachers.teacher_id"), nullable=True, index=True
    )
    room: Mapped[str] = mapped_column(String(100), default="Por asignar")
    capacity: Mapped[int] = mapped_column(Integer, default=35)
    status: Mapped[str] = mapped_column(String(20), default="active")

    career: Mapped["Career"] = relationship(lazy="selectin")
    school_year: Mapped["SchoolYear"] = relationship(lazy="selectin")
    homeroom_teacher: Mapped["Teacher | None"] = relationship(lazy="selectin")
    members: Mapped[list["ClassGroupMember"]] = relationship(
        back_populates="class_group", order_by="ClassGroupMember.member_id"
    )
    subject_teachers: Mapped[list["ClassGroupSubject"]] = relationship(
        back_populates="class_group", cascade="all, delete-orphan"
    )

    @property
    def label(self) -> str:
        return f"{self.grade_number}.º {self.name} · {self.career.name}"


class ClassGroupSubject(Base):
    """Who teaches each subject of the grade in this group (default: the homeroom teacher)."""

    __tablename__ = "class_group_subjects"
    __table_args__ = (
        UniqueConstraint("class_group_id", "subject_id", name="uq_class_group_subject"),
    )

    class_group_subject_id: Mapped[int] = mapped_column(primary_key=True)
    class_group_id: Mapped[int] = mapped_column(
        ForeignKey("class_groups.class_group_id"), index=True
    )
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.subject_id"))
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.teacher_id"))

    class_group: Mapped[ClassGroup] = relationship(back_populates="subject_teachers")


class ClassGroupMember(Base):
    """A student's place in a group for one school year (one group per year)."""

    __tablename__ = "class_group_members"
    __table_args__ = (
        UniqueConstraint("student_id", "school_year_id", name="uq_class_group_member_year"),
    )

    member_id: Mapped[int] = mapped_column(primary_key=True)
    class_group_id: Mapped[int] = mapped_column(
        ForeignKey("class_groups.class_group_id"), index=True
    )
    student_id: Mapped[int] = mapped_column(ForeignKey("students.student_id"), index=True)
    # Copy of the group's year so the database enforces one group per year.
    school_year_id: Mapped[int] = mapped_column(ForeignKey("school_years.school_year_id"))
    status: Mapped[str] = mapped_column(String(20), default="enrolled")
    joined_on: Mapped[date] = mapped_column(Date)
    left_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    result: Mapped[str] = mapped_column(String(20), default="pending")
    result_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    result_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    class_group: Mapped[ClassGroup] = relationship(back_populates="members")
    student: Mapped["Student"] = relationship(lazy="selectin")
