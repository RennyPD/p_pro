from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


class ClassGroupBase(BaseModel):
    career_id: int
    grade_number: int = Field(ge=1, le=20)
    name: str = Field(min_length=1, max_length=20)
    school_year_id: int
    homeroom_teacher_id: int | None = None
    room: str = Field(default="Por asignar", max_length=100)
    capacity: int = Field(default=35, ge=1, le=80)
    shift: str = Field(default="", pattern=r"^(|matutina|vespertina|extendida|nocturna)$")

    @model_validator(mode="after")
    def clean(self):
        self.name = self.name.strip().upper()
        if not self.name:
            raise ValueError("El grupo necesita un nombre")
        return self


class ClassGroupCreate(ClassGroupBase):
    pass


class ClassGroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=20)
    homeroom_teacher_id: int | None = None
    room: str | None = Field(default=None, max_length=100)
    capacity: int | None = Field(default=None, ge=1, le=80)
    status: str | None = Field(default=None, pattern=r"^(active|closed)$")
    shift: str | None = Field(default=None, pattern=r"^(|matutina|vespertina|extendida|nocturna)$")


class ClassGroupOut(ClassGroupBase):
    class_group_id: int
    status: str
    label: str
    career_name: str
    school_year_name: str
    homeroom_teacher_name: str | None = None
    member_count: int = 0


class ClassGroupMemberOut(BaseModel):
    member_id: int
    student_id: int
    student_name: str
    enrollment_number: str
    status: str
    joined_on: date
    left_on: date | None = None
    result: str
    result_confirmed_at: datetime | None = None
    result_note: str | None = None
    financial_hold: bool = False
    academic_hold: bool = False


class ClassGroupSubjectOut(BaseModel):
    subject_id: int
    code: str
    name: str
    teacher_id: int | None = None
    teacher_name: str | None = None
    sections: int = 0


class ClassGroupDetail(ClassGroupOut):
    members: list[ClassGroupMemberOut]
    subjects: list[ClassGroupSubjectOut]
    open_periods: list[str]


class SubjectTeacherIn(BaseModel):
    teacher_id: int


class MemberAdd(BaseModel):
    student_id: int
    override_reason: str | None = Field(default=None, max_length=250)


class MemberChange(BaseModel):
    reason: str = Field(min_length=3, max_length=250)


class MemberTransfer(MemberChange):
    target_group_id: int


class SubjectsGenerated(BaseModel):
    sections_created: int
    enrollments_created: int


class SubjectResultOut(BaseModel):
    subject_id: int
    code: str
    name: str
    periods: list[float | None]
    average: float | None
    average_label: str | None = None
    complete: bool
    passed: bool | None
    status: str
    completivo: float | None = None
    extraordinario: float | None = None
    especial: float | None = None


class PromotionRow(BaseModel):
    member_id: int
    student_id: int
    student_name: str
    enrollment_number: str
    subjects: list[SubjectResultOut]
    failed: list[str]
    complete: bool
    proposal: str | None
    result: str
    confirmed: bool


class PromotionProposal(BaseModel):
    class_group_id: int
    passing_grade: float
    scale_name: str
    completivo_average_weight: float
    extraordinario_average_weight: float
    periods: list[str]
    members: list[PromotionRow]


class ResultDecision(BaseModel):
    member_id: int
    result: str = Field(pattern=r"^(promoted|completivo|extraordinario|repeated)$")
    note: str | None = Field(default=None, max_length=250)


class ResultConfirmation(BaseModel):
    decisions: list[ResultDecision] = Field(min_length=1)


class RecoveryIn(BaseModel):
    subject_id: int
    kind: str = Field(pattern=r"^(completivo|extraordinario|especial)$")
    exam_grade: Decimal = Field(ge=0, le=100, max_digits=5, decimal_places=2)


class ReinscriptionIn(BaseModel):
    target_group_id: int
    member_ids: list[int] = Field(min_length=1)
    override_reason: str | None = Field(default=None, max_length=250)


class BlockedStudent(BaseModel):
    student_name: str
    reason: str


class ReinscriptionOut(BaseModel):
    reinscribed: list[str]
    blocked: list[BlockedStudent]
