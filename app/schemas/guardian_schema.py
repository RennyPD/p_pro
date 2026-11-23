"""Detail a guardian sees of each linked student (audit A1, M8)."""

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.academic_schema import AttendanceCourseSummary, ScheduleBlock
from app.schemas.finance_schema import Amount, Money, Reference, StudentFinanceSummary
from app.schemas.grading_scale_schema import ScaleBrief


class GuardianAttendance(BaseModel):
    student_id: int
    period: str | None
    present_count: int
    total_count: int
    percentage: float | None
    counts: dict[str, int]
    courses: list[AttendanceCourseSummary]


class GuardianAssessment(BaseModel):
    assessment_id: int | None
    name: str
    weight: float | None
    due_date: date | None
    grade_value: float | None
    contribution: float | None
    grade_label: str | None = None


class GuardianCourseGrades(BaseModel):
    enrollment_id: int
    section_code: str
    subject_code: str
    subject_name: str
    state: str
    result: float | None
    result_status: str
    final: bool
    completed_weight: float
    configured_weight: float
    assessments: list[GuardianAssessment]
    result_label: str | None = None


class GuardianGrades(BaseModel):
    student_id: int
    period: str | None
    courses: list[GuardianCourseGrades]
    grading_scale: ScaleBrief | None = None


class GuardianTask(BaseModel):
    assignment_id: int
    title: str
    subject_name: str
    section_code: str
    due_at: datetime
    max_score: float
    status: str  # pending | overdue | submitted | graded
    submitted_at: datetime | None
    score: float | None
    feedback: str


class GuardianFinance(StudentFinanceSummary):
    next_due_date: date | None
    next_due_amount: float | None
    financial_responsible: bool


class GuardianPeriodPerformance(BaseModel):
    period: str
    average_grade: float | None
    final_grade_count: int
    provisional_average_grade: float | None
    provisional_grade_count: int
    attendance_percentage: float | None
    course_count: int


class GuardianAlert(BaseModel):
    early_alert_id: int
    category: str
    severity: str
    reason: str
    follow_up_date: date | None


class GuardianPerformance(BaseModel):
    student_id: int
    periods: list[GuardianPeriodPerformance]
    alerts: list[GuardianAlert]


class GuardianScheduleItem(BaseModel):
    section_id: int
    section_code: str
    subject_name: str
    days_of_week: str
    start_time: str
    end_time: str
    room: str
    modality: str
    blocks: list[ScheduleBlock]


class GuardianAreas(BaseModel):
    academic: bool
    attendance: bool
    finance: bool
    tasks: bool


class GuardianStudentOverview(BaseModel):
    student_id: int
    student_name: str
    enrollment_number: str
    career_name: str
    active: bool
    permissions: GuardianAreas
    average_grade: float | None
    final_grade_count: int
    provisional_average_grade: float | None
    provisional_grade_count: int
    attendance_percentage: float | None
    attendance_count: int
    metrics_period: str | None
    balance: float | None
    schedule: list[GuardianScheduleItem]
    alerts: list[GuardianAlert]


class FamilyStudentBalance(BaseModel):
    student_id: int
    student_name: str
    enrollment_number: str
    balance: Amount
    overdue_balance: Amount
    next_due_date: date | None
    next_due_amount: Amount | None
    financial_responsible: bool


class FamilyConceptShare(BaseModel):
    student_id: int
    remaining: Amount


class FamilyConcept(BaseModel):
    concept: str
    remaining: Amount
    students: list[FamilyConceptShare]


class FamilyFinance(BaseModel):
    total_balance: Amount
    total_overdue: Amount
    next_due_date: date | None
    students: list[FamilyStudentBalance]
    concepts: list[FamilyConcept]


class FamilyAllocation(BaseModel):
    student_id: int
    amount: Money


class FamilySuggestion(BaseModel):
    student_id: int
    amount: Amount


class FamilyTransferCreate(BaseModel):
    reference: Reference
    bank: Reference
    note: str = Field(default="", max_length=250)
    proof_base64: str = Field(min_length=1, max_length=2800000)
    allocations: list[FamilyAllocation] = Field(min_length=1, max_length=20)


class FamilyTransferShare(BaseModel):
    transfer_request_id: int
    student_id: int
    student_name: str
    amount: Amount
    status: str


class FamilyTransferOut(BaseModel):
    transfer_batch_id: int
    reference: str
    bank: str
    total: Amount
    status: str
    submitted_at: datetime
    review_reason: str | None
    shares: list[FamilyTransferShare]
