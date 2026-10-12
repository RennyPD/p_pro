from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import ensure_student_academic_access, get_current_user, require_permissions
from app.db.Session import get_db
from app.models.career_model import Career
from app.models.curriculum_model import CurriculumCourse
from app.models.student_model import Student
from app.models.subject_model import Subject
from app.models.user_model import User
from app.schemas.curriculum_schema import (
    CurriculumCourseCreate,
    CurriculumCourseOut,
    CurriculumCourseUpdate,
    CurriculumProgress,
    CurriculumProgressItem,
)
from app.services.academic_grading import academic_result
from app.services.academic_recognition import current_courses, recognize

router = APIRouter(prefix="/curriculum", tags=["curriculum"])
curriculum_manager = require_permissions("academic.manage", fallback_roles=("admin",))


def course_out(course: CurriculumCourse) -> CurriculumCourseOut:
    return CurriculumCourseOut(
        curriculum_course_id=course.curriculum_course_id,
        career_id=course.career_id,
        subject_id=course.subject_id,
        term_number=course.term_number,
        credits=course.credits,
        course_type=course.course_type,
        curriculum_version=course.curriculum_version,
        prerequisite_subject_id=course.prerequisite_subject_id,
        corequisite_subject_id=course.corequisite_subject_id,
        subject_code=course.subject.code,
        subject_name=course.subject.description,
        prerequisite_code=course.prerequisite.code if course.prerequisite else None,
        corequisite_code=course.corequisite.code if course.corequisite else None,
    )


@router.post(
    "/courses", response_model=CurriculumCourseOut, dependencies=[Depends(curriculum_manager)]
)
def add_curriculum_course(data: CurriculumCourseCreate, db: Session = Depends(get_db)):
    validate_curriculum_course(db, data.model_dump())
    if (
        db.query(CurriculumCourse)
        .filter_by(career_id=data.career_id, subject_id=data.subject_id)
        .first()
    ):
        raise HTTPException(
            status_code=409,
            detail="Esta asignatura ya pertenece al pensum de la carrera. Edita el registro existente.",
        )
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
    dependencies=[Depends(curriculum_manager)],
)
def update_curriculum_course(
    course_id: int, data: CurriculumCourseUpdate, db: Session = Depends(get_db)
):
    course = db.get(CurriculumCourse, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Curriculum course not found")
    changes = data.model_dump(exclude_unset=True)
    values = {key: getattr(course, key) for key in CurriculumCourseCreate.model_fields}
    values.update(changes)
    validate_curriculum_course(db, values)
    for key, value in changes.items():
        setattr(course, key, value)
    if course.subject_id in {course.prerequisite_subject_id, course.corequisite_subject_id}:
        raise HTTPException(status_code=422, detail="A subject cannot require itself")
    db.commit()
    db.refresh(course)
    return course_out(course)


def validate_curriculum_course(db: Session, values: dict):
    career = db.get(Career, values["career_id"])
    if career is None:
        raise HTTPException(status_code=404, detail="Carrera no encontrada")
    for field in ("subject_id", "prerequisite_subject_id", "corequisite_subject_id"):
        identifier = values[field]
        if identifier is not None and db.get(Subject, identifier) is None:
            raise HTTPException(status_code=404, detail="Asignatura o requisito no encontrado")
    if values["subject_id"] in {
        values["prerequisite_subject_id"],
        values["corequisite_subject_id"],
    }:
        raise HTTPException(
            status_code=422, detail="Una asignatura no puede ser requisito de sí misma"
        )
    if values["term_number"] is None or values["term_number"] > career.duration_terms:
        raise HTTPException(
            status_code=422,
            detail="El período recomendado debe estar dentro de la duración de la carrera",
        )
    if any(values[field] is None for field in ("credits", "course_type", "curriculum_version")):
        raise HTTPException(status_code=422, detail="Créditos, tipo y versión son obligatorios")
    if not values["curriculum_version"].strip():
        raise HTTPException(status_code=422, detail="La versión del pensum no puede estar vacía")


@router.delete("/courses/{course_id}", dependencies=[Depends(curriculum_manager)])
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
    courses = current_courses(db, student)
    recognition = recognize(db, student)
    results = []
    completed_credits = 0.0
    for course in courses:
        matching = [
            enrollment
            for enrollment in student.enrollments
            if enrollment.section.subject_id == course.subject_id
        ]
        calculations = [academic_result(db, enrollment) for enrollment in matching]
        finals = [item.value for item in calculations if item.final and item.value is not None]
        average = max(finals) if finals else None
        if course.subject_id in recognition.completed:
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
                corequisite_code=course.corequisite.code if course.corequisite else None,
                course_type=course.course_type,
                curriculum_version=course.curriculum_version,
                status=status,
                final_average=average,
                recognition_type="equivalence"
                if course.subject_id in recognition.paths
                else "direct"
                if course.subject_id in recognition.direct
                else "pending",
                equivalence_ids=recognition.paths.get(course.subject_id, []),
            )
        )
        if course.subject_id in recognition.paths:
            results[-1].final_average = None
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
