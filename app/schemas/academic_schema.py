from datetime import date, time

from pydantic import BaseModel


class GradeHistoryItem(BaseModel):
    grade_id: int
    enrollment_id: int
    subject_code: str
    section_code: str
    period: str
    grade_value: float
    grade_type: str
    date_recorded: str


class ScheduleItem(BaseModel):
    section_id: int
    section_code: str
    subject_code: str
    days_of_week: list[str]
    start_time: time
    end_time: time


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


class StudentAcademicProfile(BaseModel):
    student_id: int
    enrollment_number: str
    first_name: str
    last_name: str
    email: str
    telephone: str
    address: str
    active: bool
    career_id: int
    career_name: str
    overall_average: float | None
    overall_attendance: float | None
    enrollments: list[StudentEnrollmentSummary]


class RosterGradeItem(BaseModel):
    grade_id: int
    grade_type: str
    grade_value: float
    date_recorded: str


class SectionRosterItem(SectionStudentItem):
    email: str
    grades: list[RosterGradeItem]
    average_grade: float | None
    attendance_percentage: float | None
    attendance_status: bool | None


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


class AttendanceCourseSummary(BaseModel):
    section_id: int
    section_code: str
    subject_code: str
    subject_name: str
    present_count: int
    total_count: int
    percentage: float | None
