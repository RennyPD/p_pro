from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import ensure_student_academic_access, get_current_user, require_roles
from app.db.Session import get_db
from app.models.career_model import Career
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

router = APIRouter(prefix="/governance", tags=["academic governance"])
router.include_router(equivalence_routes)


@router.post("/students/{student_id}/career-change", response_model=CareerHistoryOut)
def change_student_career(
    student_id: int,
    data: CareerChangeCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    student = db.get(Student, student_id)
    target = db.get(Career, data.new_career_id)
    if student is None or target is None:
        raise HTTPException(status_code=404, detail="Student or career not found")
    if student.career_id == target.career_id:
        raise HTTPException(status_code=409, detail="Student already belongs to this career")
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
    db.add(item)
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
    ensure_student_academic_access(db, user, student_id)
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
    ensure_student_academic_access(db, user, student_id)
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")
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
        curriculum_version=student.career.curriculum_version,
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
