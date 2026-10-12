from datetime import date, time

from pydantic import BaseModel

from app.schemas.student_schema import StudentDossierFields


class GradeHistoryItem(BaseModel):
    grade_id: int
    enrollment_id: int
    subject_code: str
    section_code: str
    period: str
    grade_value: float
    grade_type: str
    date_recorded: str
    assessment_weight: float | None = None
    contribution: float | None = None


class ScheduleItem(BaseModel):
    section_id: int
    section_code: str
    subject_code: str
    subject_name: str
    teacher_name: str
    room: str
    modality: str
    days_of_week: list[str]
    start_time: time
    end_time: time


class CourseOffering(BaseModel):
    section_id: int
    section_code: str
    subject_id: int
    subject_code: str
    subject_name: str
    teacher_name: str
    credits: int
    days_of_week: list[str]
    start_time: time
    end_time: time
    room: str
    modality: str
    capacity: int
    available_seats: int
    selection_status: str | None
    waitlist_position: int | None = None
    period: str
    section_status: str
    prerequisite_code: str | None
    corequisite_code: str | None
    selectable: bool
    restriction_reason: str | None


class CourseSelectionSummary(BaseModel):
    period: str | None
    period_status: str | None
    selected_credits: float
    maximum_credits: int
    enrolled_sections: int
    waitlisted_sections: int
    cart_sections: int = 0
    cart_credits: float = 0


class CartItemOut(BaseModel):
    cart_item_id: int
    section_id: int
    section_code: str
    subject_code: str
    subject_name: str
    credits: float
    available_seats: int
    period: str


class SectionStudentItem(BaseModel):
    student_id: int
    enrollment_id: int
    enrollment_number: str
    first_name: str
    last_name: str
    state: str
    period: str


class StudentEnrollmentSummary(BaseModel):
    enrollment_id: int
    section_id: int
    section_code: str
    subject_code: str
    subject_name: str
    period: str
    state: str
    average_grade: float | None
    attendance_percentage: float | None
    result_final: bool = False
    result_status: str = "in_progress"
    completed_weight: float = 0
    calculation_mode: str = "weighted"


class StudentAcademicProfile(StudentDossierFields):
    student_id: int
    enrollment_number: str
    first_name: str
    last_name: str
    email: str
    telephone: str
    address: str
    active: bool
    academic_hold: bool = False
    financial_hold: bool = False
    career_id: int
    career_name: str
    overall_average: float | None
    overall_attendance: float | None
    enrollments: list[StudentEnrollmentSummary]


class RosterGradeItem(BaseModel):
    grade_id: int
    assessment_id: int | None
    grade_type: str
    grade_value: float
    date_recorded: str
    status: str = "published"
    assessment_weight: float | None = None
    contribution: float | None = None


class RosterAttendanceItem(BaseModel):
    attendance_id: int
    date: date
    status: str
    note: str
    excuse_reference: str = ""


class SectionRosterItem(SectionStudentItem):
    email: str
    grades: list[RosterGradeItem]
    average_grade: float | None
    attendance_percentage: float | None
    attendance_status: bool | None
    attendances: list[RosterAttendanceItem]
    result_final: bool = False
    result_status: str = "in_progress"
    completed_weight: float = 0
    calculation_mode: str = "weighted"


class SectionAcademicSummary(BaseModel):
    section_id: int
    section_code: str
    subject_code: str
    subject_name: str
    teacher_name: str
    student_count: int
    attendance_percentage: float | None
    grade_average: float | None
    assessment_count: int
    period_name: str = ""
    graded_student_count: int = 0
    final_student_count: int = 0
    pending_student_count: int = 0
    draft_grade_count: int = 0
    published_grade_count: int = 0
    closed_assessment_count: int = 0
    configured_weight: float = 0
    attendance_total: int = 0
    attendance_counts: dict[str, int] = {}


class SectionWorkspace(BaseModel):
    section_id: int
    section_code: str
    description: str
    subject_code: str
    subject_name: str
    teacher_name: str
    days_of_week: list[str]
    start_time: time
    end_time: time
    attendance_date: date
    roster: list[SectionRosterItem]
    subject_id: int = 0
    period_name: str = ""


class AttendanceCourseSummary(BaseModel):
    section_id: int
    section_code: str
    subject_code: str
    subject_name: str
    present_count: int
    total_count: int
    percentage: float | None
    enrollment_id: int = 0
    period: str = ""
    state: str = "enrolled"
    counts: dict[str, int] = {}
    records: list[RosterAttendanceItem] = []
