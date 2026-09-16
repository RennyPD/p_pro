from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import (
    ensure_section_access,
    ensure_student_academic_access,
    ensure_teacher_access,
    get_current_user,
)
from app.db.Session import get_db
from app.models.enrollment_model import Enrollment
from app.models.grade_model import Grade
from app.models.section_model import Section
from app.models.user_model import User
from app.schemas.academic_schema import GradeHistoryItem, ScheduleItem, SectionStudentItem

router = APIRouter(prefix="/academic", tags=["academic queries"])


def schedule_item(section: Section) -> ScheduleItem:
    return ScheduleItem(
        section_id=section.section_id,
        section_code=section.code,
        subject_code=section.subject.code,
        days_of_week=section.days_of_week.split(", "),
        start_time=section.start_time,
        end_time=section.end_time,
    )


@router.get("/students/{student_id}/grades", response_model=list[GradeHistoryItem])
def student_grade_history(
    student_id: int,
    period: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_student_academic_access(db, user, student_id)
    query = db.query(Grade).join(Grade.enrollment).filter(Enrollment.student_id == student_id)
    if period:
        query = query.filter(Enrollment.period == period)
    grades = query.offset(skip).limit(limit).all()
    return [
        GradeHistoryItem(
            grade_id=grade.grade_id,
            enrollment_id=grade.enrollment_id,
            subject_code=grade.enrollment.section.subject.code,
            section_code=grade.enrollment.section.code,
            period=grade.enrollment.period,
            grade_value=grade.grade_value,
            grade_type=grade.grade_type,
            date_recorded=grade.date_recorded,
        )
        for grade in grades
    ]


@router.get("/students/{student_id}/schedule", response_model=list[ScheduleItem])
def student_schedule(
    student_id: int,
    period: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_student_academic_access(db, user, student_id)
    query = db.query(Section).join(Section.enrollments).filter(Enrollment.student_id == student_id)
    if period:
        query = query.filter(Enrollment.period == period)
    return [schedule_item(section) for section in query.distinct().all()]


@router.get("/teachers/{teacher_id}/schedule", response_model=list[ScheduleItem])
def teacher_schedule(
    teacher_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_teacher_access(user, teacher_id)
    return [
        schedule_item(section)
        for section in db.query(Section).filter(Section.teacher_id == teacher_id).all()
    ]


@router.get("/sections/{section_id}/students", response_model=list[SectionStudentItem])
def section_students(
    section_id: int,
    period: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_section_access(db, user, section_id)
    query = db.query(Enrollment).filter(Enrollment.section_id == section_id)
    if period:
        query = query.filter(Enrollment.period == period)
    enrollments = query.offset(skip).limit(limit).all()
    return [
        SectionStudentItem(
            student_id=item.student_id,
            enrollment_id=item.enrollment_id,
            enrollment_number=item.student.enrollment_number,
            first_name=item.student.first_name,
            last_name=item.student.last_name,
            state=item.state,
            period=item.period,
        )
        for item in enrollments
    ]
