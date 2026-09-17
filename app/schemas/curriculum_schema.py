from pydantic import BaseModel, Field


class CurriculumCourseBase(BaseModel):
    career_id: int
    subject_id: int
    term_number: int = Field(ge=1, le=30)
    credits: float = Field(gt=0, le=30)
    prerequisite_subject_id: int | None = None


class CurriculumCourseCreate(CurriculumCourseBase):
    pass


class CurriculumCourseUpdate(BaseModel):
    term_number: int | None = Field(default=None, ge=1, le=30)
    credits: float | None = Field(default=None, gt=0, le=30)
    prerequisite_subject_id: int | None = None


class CurriculumCourseOut(CurriculumCourseBase):
    curriculum_course_id: int
    subject_code: str
    subject_name: str
    prerequisite_code: str | None


class CurriculumProgressItem(BaseModel):
    curriculum_course_id: int
    subject_id: int
    subject_code: str
    subject_name: str
    term_number: int
    credits: float
    prerequisite_code: str | None
    status: str
    final_average: float | None


class CurriculumProgress(BaseModel):
    student_id: int
    career_name: str
    total_credits: float
    completed_credits: float
    progress_percentage: float
    courses: list[CurriculumProgressItem]
