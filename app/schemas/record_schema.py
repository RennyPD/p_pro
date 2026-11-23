from pydantic import BaseModel, Field


class PeriodRecord(BaseModel):
    period: str
    average: float | None
    attempted_credits: float
    earned_credits: float
    courses: int


class TranscriptCourse(BaseModel):
    recognition_type: str = "direct"
    equivalence_ids: list[int] = Field(default_factory=list)
    origin_subject_code: str | None = None
    subject_code: str
    subject_name: str
    section_code: str
    period: str
    credits: float | None
    curriculum_version: str | None = None
    average: float | None
    result: str
    attempts: int
    average_label: str | None = None


class AcademicTranscript(BaseModel):
    unverified_credit_courses: int = 0
    recognized_credits: float = 0
    curriculum_version: str = "current"
    student_id: int
    enrollment_number: str
    student_name: str
    career_name: str
    cumulative_average: float | None
    final_result_count: int = 0
    provisional_average: float | None = None
    provisional_result_count: int = 0
    attempted_credits: float
    earned_credits: float
    repeated_courses: int
    academic_standing: str
    periods: list[PeriodRecord]
    courses: list[TranscriptCourse]
    grading_scale_name: str | None = None
    # Credit-weighted index (0–4 with letter scales); None without band points.
    academic_index: float | None = None
