from datetime import time

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
