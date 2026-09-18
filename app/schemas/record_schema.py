from pydantic import BaseModel


class PeriodRecord(BaseModel):
    period: str
    average: float
    attempted_credits: float
    earned_credits: float
    courses: int


class TranscriptCourse(BaseModel):
    subject_code: str
    subject_name: str
    section_code: str
    period: str
    credits: float
    average: float | None
    result: str
    attempts: int


class AcademicTranscript(BaseModel):
    student_id: int
    enrollment_number: str
    student_name: str
    career_name: str
    cumulative_average: float
    attempted_credits: float
    earned_credits: float
    repeated_courses: int
    academic_standing: str
    periods: list[PeriodRecord]
    courses: list[TranscriptCourse]
