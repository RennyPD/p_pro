from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.auth import ensure_student_access, get_current_user, require_permissions
from app.db.Session import get_db
from app.models.career_model import Career
from app.models.curriculum_model import CurriculumCourse
from app.models.enrollment_model import Enrollment
from app.models.student_model import Student
from app.models.subject_model import Subject
from app.models.user_model import User
from app.pagination import page_query
from app.schemas.curriculum_schema import (
    CurriculumCourseCreate,
    CurriculumCourseOut,
    CurriculumCourseUpdate,
    CurriculumProgress,
    CurriculumProgressItem,
)
from app.services.academic_grading import academic_result
from app.services.academic_recognition import current_courses, recognize
from app.services.governance_workflow import lock_governance, record

router = APIRouter(prefix="/curriculum", tags=["curriculum"])
curriculum_manager = require_permissions("programs.manage")
assignment_admin = Depends(require_permissions("students.manage"))
Version = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=250)]


class CurriculumAssignment(BaseModel):
    version: Version
    reason: Reason


class VerifiedCredits(CurriculumAssignment):
    credits: float = Field(ge=0, allow_inf_nan=False)


def curriculum_student(db, student_id):
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(404, "El expediente ya no está disponible")
    return student


@router.get(
    "/students/{student_id}/assignment",
    dependencies=[assignment_admin, Depends(curriculum_manager)],
)
def curriculum_assignment(student_id: int, db: Session = Depends(get_db)):
    student = curriculum_student(db, student_id)
    versions = (
        db.query(CurriculumCourse.curriculum_version)
        .filter_by(career_id=student.career_id)
        .distinct()
        .all()
    )
    return {
        "assigned_version": student.assigned_curriculum_version,
        "operative_version": student.curriculum_version,
        "versions": sorted(row[0] for row in versions),
        "unverified": [
            {
                "enrollment_id": item.enrollment_id,
                "period": item.period,
                "section_code": item.section.code,
                "subject_name": item.section.subject.description,
            }
            for item in student.enrollments
            if item.curriculum_credits is None and item.state not in {"withdrawn", "waitlisted"}
        ],
    }


@router.put("/students/{student_id}/assignment", dependencies=[assignment_admin])
def assign_curriculum(
    student_id: int,
    data: CurriculumAssignment,
    db: Session = Depends(get_db),
    actor: User = Depends(curriculum_manager),
):
    lock_governance(db)
    student = curriculum_student(db, student_id)
    if (
        db.query(CurriculumCourse)
        .filter_by(career_id=student.career_id, curriculum_version=data.version)
        .first()
        is None
    ):
        raise HTTPException(422, "Selecciona una versión publicada en el catálogo de esta carrera")
    previous = student.assigned_curriculum_version or "pendiente"
    student.assigned_curriculum_version = data.version
    record(
        db,
        actor,
        "curriculum.assigned",
        f"student:{student_id}",
        f"{previous} → {data.version}. {data.reason}",
    )
    db.commit()
    return {"assigned_version": data.version}


@router.put(
    "/students/{student_id}/enrollments/{enrollment_id}/verified-credits",
    dependencies=[assignment_admin],
)
def verify_credits(
    student_id: int,
    enrollment_id: int,
    data: VerifiedCredits,
    db: Session = Depends(get_db),
    actor: User = Depends(curriculum_manager),
):
    lock_governance(db)
    entry = db.get(Enrollment, enrollment_id)
    if entry is None or entry.student_id != student_id:
        raise HTTPException(404, "La inscripción no pertenece a este expediente")
    if entry.state in {"withdrawn", "waitlisted"}:
        raise HTTPException(
            409, "Verifica créditos únicamente para inscripciones que figuran en el historial"
        )
    if entry.curriculum_credits is not None:
        raise HTTPException(409, "La inscripción ya tiene créditos respaldados")
    entry.curriculum_credits = data.credits
    entry.curriculum_version = data.version
    record(
        db,
        actor,
        "curriculum.credits_verified",
        f"enrollment:{enrollment_id}",
        f"Versión {data.version}, {data.credits:g} créditos. {data.reason}",
    )
    db.commit()
    return {"credits": data.credits}


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
    lock_governance(db)
    validate_curriculum_course(db, data.model_dump())
    if (
        db.query(CurriculumCourse)
        .filter_by(
            career_id=data.career_id,
            subject_id=data.subject_id,
            curriculum_version=data.curriculum_version,
        )
        .first()
    ):
        raise HTTPException(
            status_code=409,
            detail="Esta asignatura ya pertenece a esta versión del pensum. Edita el registro existente.",
        )
    course = CurriculumCourse(**data.model_dump())
    db.add(course)
    db.commit()
    db.refresh(course)
    return course_out(course)


@router.get("/courses", response_model=list[CurriculumCourseOut])
def list_curriculum_courses(
    response: Response,
    career_id: int | None = None,
    q: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int | None = Query(None, ge=1, le=100),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    query = db.query(CurriculumCourse).options(
        joinedload(CurriculumCourse.subject),
        joinedload(CurriculumCourse.prerequisite),
        joinedload(CurriculumCourse.corequisite),
    )
    if career_id is not None:
        query = query.filter(CurriculumCourse.career_id == career_id)
    if q and (term := q.strip()):
        query = query.join(CurriculumCourse.subject).filter(
            or_(
                Subject.code.icontains(term, autoescape=True),
                Subject.description.icontains(term, autoescape=True),
            )
        )
    rows = page_query(
        query.order_by(CurriculumCourse.term_number, CurriculumCourse.curriculum_course_id),
        response,
        skip,
        limit,
    )
    return [course_out(item) for item in rows]


@router.patch(
    "/courses/{course_id}",
    response_model=CurriculumCourseOut,
    dependencies=[Depends(curriculum_manager)],
)
def update_curriculum_course(
    course_id: int, data: CurriculumCourseUpdate, db: Session = Depends(get_db)
):
    lock_governance(db)
    course = db.get(CurriculumCourse, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Asignatura del plan de estudios no encontrada")
    changes = data.model_dump(exclude_unset=True)
    values = {key: getattr(course, key) for key in CurriculumCourseCreate.model_fields}
    values.update(changes)
    validate_curriculum_course(db, values, course_id=course_id)
    if (values["career_id"], values["curriculum_version"]) != (
        course.career_id,
        course.curriculum_version,
    ):
        ensure_assigned_version_remains(db, course)
    for key, value in changes.items():
        setattr(course, key, value)
    db.commit()
    db.refresh(course)
    return course_out(course)


def ensure_assigned_version_remains(db: Session, course: CurriculumCourse):
    other_course = (
        db.query(CurriculumCourse.curriculum_course_id)
        .filter_by(career_id=course.career_id, curriculum_version=course.curriculum_version)
        .filter(CurriculumCourse.curriculum_course_id != course.curriculum_course_id)
        .first()
    )
    if (
        other_course is None
        and db.query(Student.student_id)
        .filter_by(
            career_id=course.career_id, assigned_curriculum_version=course.curriculum_version
        )
        .first()
    ):
        raise HTTPException(
            409, "Reasigna los expedientes antes de retirar la última asignatura de esta versión"
        )


def validate_curriculum_course(db: Session, values: dict, *, course_id: int | None = None):
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
    if course_id is not None and (
        db.query(CurriculumCourse.curriculum_course_id)
        .filter_by(
            career_id=career.career_id,
            subject_id=values["subject_id"],
            curriculum_version=values["curriculum_version"],
        )
        .filter(CurriculumCourse.curriculum_course_id != course_id)
        .first()
    ):
        raise HTTPException(409, "Esta asignatura ya pertenece a esta versión del pensum")
    prerequisite = values["prerequisite_subject_id"]
    if prerequisite is None:
        return
    edges = dict(
        db.query(CurriculumCourse.subject_id, CurriculumCourse.prerequisite_subject_id)
        .filter_by(career_id=career.career_id, curriculum_version=values["curriculum_version"])
        .filter(CurriculumCourse.curriculum_course_id != course_id)
        .all()
    )
    visited = {values["subject_id"]}
    while prerequisite is not None:
        if prerequisite in visited:
            raise HTTPException(
                422, "Ese prerrequisito forma un ciclo dentro de esta versión del pensum"
            )
        visited.add(prerequisite)
        prerequisite = edges.get(prerequisite)


@router.delete("/courses/{course_id}", dependencies=[Depends(curriculum_manager)])
def delete_curriculum_course(course_id: int, db: Session = Depends(get_db)):
    lock_governance(db)
    course = db.get(CurriculumCourse, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Asignatura del plan de estudios no encontrada")
    ensure_assigned_version_remains(db, course)
    db.delete(course)
    db.commit()
    return {"message": "Asignatura retirada del plan de estudios"}


@router.get("/students/{student_id}/progress", response_model=CurriculumProgress)
def student_curriculum_progress(
    student_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_student_access(user, student_id)
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")
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
