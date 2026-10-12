from pydantic import BaseModel, Field


class CurriculumCourseBase(BaseModel):
    career_id: int
    subject_id: int
    term_number: int = Field(ge=1, le=30)
    credits: float = Field(gt=0, le=30)
    prerequisite_subject_id: int | None = None
    corequisite_subject_id: int | None = None
    course_type: str = Field(
        default="required", pattern=r"^(required|elective|internship|capstone)$"
    )
    curriculum_version: str = "current"


class CurriculumCourseCreate(CurriculumCourseBase):
    pass


class CurriculumCourseUpdate(BaseModel):
    term_number: int | None = Field(default=None, ge=1, le=30)
    credits: float | None = Field(default=None, gt=0, le=30)
    prerequisite_subject_id: int | None = None
    corequisite_subject_id: int | None = None
    course_type: str | None = Field(
        default=None, pattern=r"^(required|elective|internship|capstone)$"
    )
    curriculum_version: str | None = None


class CurriculumCourseOut(CurriculumCourseBase):
    curriculum_course_id: int
    subject_code: str
    subject_name: str
    prerequisite_code: str | None
    corequisite_code: str | None


class CurriculumProgressItem(BaseModel):
    recognition_type: str = "direct"
    equivalence_ids: list[int] = Field(default_factory=list)
    curriculum_course_id: int
    subject_id: int
    subject_code: str
    subject_name: str
    term_number: int
    credits: float
    prerequisite_code: str | None
    corequisite_code: str | None
    course_type: str
    curriculum_version: str
    status: str
    final_average: float | None


class CurriculumProgress(BaseModel):
    student_id: int
    career_name: str
    total_credits: float
    completed_credits: float
    progress_percentage: float
    courses: list[CurriculumProgressItem]
