from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import ensure_student_academic_access, get_current_user, require_roles
from app.db.Session import get_db
from app.models.configuration_model import InstitutionSettings
from app.models.curriculum_model import CurriculumCourse
from app.models.student_model import Student
from app.models.user_model import User
from app.schemas.curriculum_schema import (
    CurriculumCourseCreate,
    CurriculumCourseOut,
    CurriculumCourseUpdate,
    CurriculumProgress,
    CurriculumProgressItem,
)

router = APIRouter(prefix="/curriculum", tags=["curriculum"])


def course_out(course: CurriculumCourse) -> CurriculumCourseOut:
    return CurriculumCourseOut(
        curriculum_course_id=course.curriculum_course_id,
        career_id=course.career_id,
        subject_id=course.subject_id,
        term_number=course.term_number,
        credits=course.credits,
        prerequisite_subject_id=course.prerequisite_subject_id,
        subject_code=course.subject.code,
        subject_name=course.subject.description,
        prerequisite_code=course.prerequisite.code if course.prerequisite else None,
    )


@router.post(
    "/courses", response_model=CurriculumCourseOut, dependencies=[Depends(require_roles("admin"))]
)
def add_curriculum_course(data: CurriculumCourseCreate, db: Session = Depends(get_db)):
    if data.subject_id == data.prerequisite_subject_id:
        raise HTTPException(status_code=422, detail="A subject cannot require itself")
    course = CurriculumCourse(**data.model_dump())
    db.add(course)
    db.commit()
    db.refresh(course)
    return course_out(course)


@router.get("/courses", response_model=list[CurriculumCourseOut])
def list_curriculum_courses(
    career_id: int | None = None,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    query = db.query(CurriculumCourse)
    if career_id is not None:
        query = query.filter(CurriculumCourse.career_id == career_id)
    return [course_out(item) for item in query.order_by(CurriculumCourse.term_number).all()]


@router.patch(
    "/courses/{course_id}",
    response_model=CurriculumCourseOut,
    dependencies=[Depends(require_roles("admin"))],
)
def update_curriculum_course(
    course_id: int, data: CurriculumCourseUpdate, db: Session = Depends(get_db)
):
    course = db.get(CurriculumCourse, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Curriculum course not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(course, key, value)
    if course.subject_id == course.prerequisite_subject_id:
        raise HTTPException(status_code=422, detail="A subject cannot require itself")
    db.commit()
    db.refresh(course)
    return course_out(course)


@router.delete("/courses/{course_id}", dependencies=[Depends(require_roles("admin"))])
def delete_curriculum_course(course_id: int, db: Session = Depends(get_db)):
    course = db.get(CurriculumCourse, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Curriculum course not found")
    db.delete(course)
    db.commit()
    return {"message": "Curriculum course deleted successfully"}


@router.get("/students/{student_id}/progress", response_model=CurriculumProgress)
def student_curriculum_progress(
    student_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_student_academic_access(db, user, student_id)
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")
    settings = db.get(InstitutionSettings, 1)
    passing_grade = settings.passing_grade if settings else 70.0
    courses = (
        db.query(CurriculumCourse)
        .filter(CurriculumCourse.career_id == student.career_id)
        .order_by(CurriculumCourse.term_number)
        .all()
    )
    results = []
    completed_credits = 0.0
    for course in courses:
        matching = [
            enrollment
            for enrollment in student.enrollments
            if enrollment.section.subject_id == course.subject_id
        ]
        grades = [grade.grade_value for enrollment in matching for grade in enrollment.grades]
        average = round(sum(grades) / len(grades), 1) if grades else None
        if average is not None and average >= passing_grade:
            status = "completed"
            completed_credits += course.credits
        elif any(enrollment.state == "enrolled" for enrollment in matching):
            status = "in_progress"
        else:
            status = "pending"
        results.append(
            CurriculumProgressItem(
                curriculum_course_id=course.curriculum_course_id,
                subject_id=course.subject_id,
                subject_code=course.subject.code,
                subject_name=course.subject.description,
                term_number=course.term_number,
                credits=course.credits,
                prerequisite_code=course.prerequisite.code if course.prerequisite else None,
                status=status,
                final_average=average,
            )
        )
    total_credits = sum(course.credits for course in courses)
    return CurriculumProgress(
        student_id=student_id,
        career_name=student.career.name,
        total_credits=total_credits,
        completed_credits=completed_credits,
        progress_percentage=round(completed_credits * 100 / total_credits, 1)
        if total_credits
        else 0,
        courses=results,
    )
