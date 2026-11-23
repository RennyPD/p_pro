from pydantic import BaseModel, Field


class ReportCardInstitution(BaseModel):
    name: str
    school_code: str
    regional: str
    district: str


class ReportCardPeriod(BaseModel):
    period_id: int
    name: str
    short: str
    closed: bool


class ReportCardSubject(BaseModel):
    subject_id: int
    code: str
    name: str
    periods: list[str | None]
    average: float | None
    average_label: str | None
    completivo: str | None
    extraordinario: str | None
    final: str | None
    status: str
    status_label: str


class ReportCardAttendance(BaseModel):
    period: str
    present: int
    late: int
    absent: int
    excused: int
    total: int
    percentage: float | None


class ReportCardComment(BaseModel):
    period_id: int
    period: str
    comment: str


class ReportCard(BaseModel):
    student_id: int
    student_name: str
    enrollment_number: str
    member_id: int
    member_status: str
    institution: ReportCardInstitution
    class_group_id: int
    group_label: str
    career_name: str
    grade_number: int
    school_year: str
    homeroom_teacher: str | None
    scale_name: str
    passing_grade: float
    periods: list[ReportCardPeriod]
    subjects: list[ReportCardSubject]
    attendance: list[ReportCardAttendance]
    comments: list[ReportCardComment]
    result: str
    result_label: str


class CommentIn(BaseModel):
    comment: str = Field(max_length=1000)


class PeriodGrade(BaseModel):
    subject_id: int
    value: float | None
    label: str | None
    final: bool


class PeriodStudent(BaseModel):
    member_id: int
    student_name: str
    enrollment_number: str
    grades: list[PeriodGrade]
    below_passing: list[str]
    attendance: float | None


class PeriodSubject(BaseModel):
    subject_id: int
    code: str
    name: str
    average: float | None
    passed_percentage: float | None
    graded: int


class PeriodReport(BaseModel):
    class_group_id: int
    group_label: str
    period_id: int
    period: str
    closed: bool
    passing_grade: float
    subjects: list[PeriodSubject]
    students: list[PeriodStudent]


class PromotionSummaryRow(BaseModel):
    class_group_id: int
    label: str
    career_name: str
    grade_number: int
    students: int
    promoted: int
    completivo: int
    extraordinario: int
    repeated: int
    pending: int
