from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import ensure_student_access, get_current_user, require_roles
from app.db.Session import get_db
from app.models.career_model import Career
from app.models.curriculum_model import CurriculumCourse
from app.models.enrollment_model import CourseSelectionCart
from app.models.governance_model import StudentCareerHistory
from app.models.student_model import Student
from app.models.user_model import User
from app.routers.equivalence_router import router as equivalence_routes
from app.schemas.governance_schema import (
    CareerChangeCreate,
    CareerHistoryOut,
    GraduationAudit,
    GraduationRequirement,
)
from app.services.academic_recognition import current_courses, recognize
from app.services.business_time import business_date
from app.services.governance_workflow import lock_governance, record

router = APIRouter(prefix="/governance", tags=["academic governance"])
router.include_router(equivalence_routes)


def career_change_impact(db, student, target):
    planned = {
        row[0]
        for row in db.query(CurriculumCourse.subject_id).filter_by(
            career_id=target.career_id, curriculum_version=target.curriculum_version
        )
    }
    cart = db.query(CourseSelectionCart).filter_by(student_id=student.student_id).all()
    return {
        "current_career": student.career.name,
        "target_career": target.name,
        "effective_date": business_date(),
        "active_selections": sum(item.state == "enrolled" for item in student.enrollments),
        "cart_outside_plan": sum(item.section.subject_id not in planned for item in cart),
    }


@router.get(
    "/students/{student_id}/career-change/preview", dependencies=[Depends(require_roles("admin"))]
)
def preview_career_change(student_id: int, career_id: int, db: Session = Depends(get_db)):
    student = db.get(Student, student_id)
    target = db.get(Career, career_id)
    if student is None or target is None:
        raise HTTPException(404, "Selecciona un estudiante y una carrera existentes")
    if student.career_id == target.career_id:
        raise HTTPException(409, "Selecciona una carrera distinta de la actual")
    return career_change_impact(db, student, target)


@router.post("/students/{student_id}/career-change", response_model=CareerHistoryOut)
def change_student_career(
    student_id: int,
    data: CareerChangeCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    lock_governance(db)
    if data.effective_date > business_date():
        raise HTTPException(422, "Registra el traslado cuando llegue su fecha efectiva")
    student = db.get(Student, student_id)
    target = db.get(Career, data.new_career_id)
    if student is None or target is None:
        raise HTTPException(status_code=404, detail="No se encontró el estudiante o la carrera")
    if student.career_id == target.career_id:
        raise HTTPException(status_code=409, detail="El estudiante ya pertenece a esta carrera")
    if data.expected_career_id is not None and student.career_id != data.expected_career_id:
        raise HTTPException(409, "La carrera actual cambió. Vuelve a consultar el expediente")
    impact = career_change_impact(db, student, target)
    previous = student.career
    item = StudentCareerHistory(
        student_id=student_id,
        previous_career_id=student.career_id,
        new_career_id=target.career_id,
        effective_date=data.effective_date,
        reason=data.reason,
        changed_by=user.user_id,
    )
    student.career_id = target.career_id
    student.assigned_curriculum_version = target.curriculum_version
    db.add(item)
    record(
        db,
        user,
        "career.changed",
        f"student:{student_id}",
        f"{previous.code} → {target.code}. Selecciones activas: {impact['active_selections']}. "
        f"Carrito fuera del plan destino: {impact['cart_outside_plan']}.",
    )
    db.commit()
    db.refresh(item)
    return CareerHistoryOut(
        **{key: value for key, value in item.__dict__.items() if not key.startswith("_")},
        previous_career_name=previous.name,
        new_career_name=target.name,
    )


@router.get("/students/{student_id}/career-history", response_model=list[CareerHistoryOut])
def career_history(
    student_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    ensure_student_access(user, student_id)
    items = (
        db.query(StudentCareerHistory)
        .filter_by(student_id=student_id)
        .order_by(StudentCareerHistory.effective_date.desc())
        .all()
    )
    return [
        CareerHistoryOut(
            **{key: value for key, value in item.__dict__.items() if not key.startswith("_")},
            previous_career_name=db.get(Career, item.previous_career_id).name,
            new_career_name=db.get(Career, item.new_career_id).name,
        )
        for item in items
    ]


@router.get("/students/{student_id}/graduation-audit", response_model=GraduationAudit)
def graduation_audit(
    student_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    ensure_student_access(user, student_id)
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="No se encontró el estudiante")
    recognition = recognize(db, student)
    passed_subjects = recognition.completed
    courses = current_courses(db, student)
    requirements = [
        GraduationRequirement(
            subject_code=item.subject.code,
            subject_name=item.subject.description,
            credits=item.credits,
            course_type=item.course_type,
            status="completed" if item.subject_id in passed_subjects else "pending",
            recognition_type="equivalence"
            if item.subject_id in recognition.paths
            else "direct"
            if item.subject_id in recognition.direct
            else "pending",
            equivalence_ids=recognition.paths.get(item.subject_id, []),
        )
        for item in courses
    ]
    earned = sum(item.credits for item in courses if item.subject_id in passed_subjects)
    required = float(student.career.required_credits or sum(item.credits for item in courses))
    return GraduationAudit(
        student_id=student_id,
        career_name=student.career.name,
        curriculum_version=student.curriculum_version,
        required_credits=required,
        earned_credits=earned,
        remaining_credits=max(required - earned, 0),
        completion_percentage=round(min(earned * 100 / required, 100), 1) if required else 0,
        eligible=earned >= required
        and all(
            item.status == "completed"
            for item in requirements
            if item.course_type in {"required", "internship", "capstone"}
        ),
        requirements=requirements,
    )
