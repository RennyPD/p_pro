from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
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
from app.models.student_model import Student
from app.models.user_model import User
from app.schemas.academic_schema import (
    AttendanceCourseSummary,
    GradeHistoryItem,
    RosterGradeItem,
    ScheduleItem,
    SectionRosterItem,
    SectionStudentItem,
    SectionWorkspace,
    StudentAcademicProfile,
    StudentEnrollmentSummary,
)

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


def _percentage(present: int, total: int) -> float | None:
    return round(present * 100 / total, 1) if total else None


@router.get("/students/{student_id}/profile", response_model=StudentAcademicProfile)
def student_academic_profile(
    student_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_student_academic_access(db, user, student_id)
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")
    summaries = []
    all_grades = []
    total_attendances = 0
    total_present = 0
    for enrollment in student.enrollments:
        grades = [grade.grade_value for grade in enrollment.grades]
        attendances = enrollment.attendances
        present = sum(item.present for item in attendances)
        all_grades.extend(grades)
        total_attendances += len(attendances)
        total_present += present
        summaries.append(
            StudentEnrollmentSummary(
                enrollment_id=enrollment.enrollment_id,
                section_id=enrollment.section_id,
                section_code=enrollment.section.code,
                subject_code=enrollment.section.subject.code,
                subject_name=enrollment.section.subject.description,
                period=enrollment.period,
                state=enrollment.state,
                average_grade=round(sum(grades) / len(grades), 1) if grades else None,
                attendance_percentage=_percentage(present, len(attendances)),
            )
        )
    return StudentAcademicProfile(
        student_id=student.student_id,
        enrollment_number=student.enrollment_number,
        first_name=student.first_name,
        last_name=student.last_name,
        email=student.email,
        telephone=student.telephone,
        address=student.address,
        active=student.active,
        career_id=student.career_id,
        career_name=student.career.name,
        overall_average=round(sum(all_grades) / len(all_grades), 1) if all_grades else None,
        overall_attendance=_percentage(total_present, total_attendances),
        enrollments=summaries,
    )


@router.get("/sections/{section_id}/workspace", response_model=SectionWorkspace)
def section_workspace(
    section_id: int,
    attendance_date: date = Query(default_factory=date.today),
    period: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    section = ensure_section_access(db, user, section_id)
    query = db.query(Enrollment).filter(Enrollment.section_id == section_id)
    if period:
        query = query.filter(Enrollment.period == period)
    roster = []
    for enrollment in query.all():
        grades = [
            RosterGradeItem(
                grade_id=item.grade_id,
                grade_type=item.grade_type,
                grade_value=item.grade_value,
                date_recorded=item.date_recorded,
            )
            for item in enrollment.grades
        ]
        attendance = next(
            (item for item in enrollment.attendances if item.date.date() == attendance_date), None
        )
        present = sum(item.present for item in enrollment.attendances)
        roster.append(
            SectionRosterItem(
                student_id=enrollment.student_id,
                enrollment_id=enrollment.enrollment_id,
                enrollment_number=enrollment.student.enrollment_number,
                first_name=enrollment.student.first_name,
                last_name=enrollment.student.last_name,
                email=enrollment.student.email,
                state=enrollment.state,
                period=enrollment.period,
                grades=grades,
                average_grade=round(sum(item.grade_value for item in grades) / len(grades), 1)
                if grades
                else None,
                attendance_percentage=_percentage(present, len(enrollment.attendances)),
                attendance_status=attendance.present if attendance else None,
            )
        )
    return SectionWorkspace(
        section_id=section.section_id,
        section_code=section.code,
        description=section.description,
        subject_code=section.subject.code,
        subject_name=section.subject.description,
        teacher_name=f"{section.teacher.first_name} {section.teacher.last_name}",
        days_of_week=section.days_of_week.split(", "),
        start_time=section.start_time,
        end_time=section.end_time,
        attendance_date=attendance_date,
        roster=roster,
    )


@router.get(
    "/students/{student_id}/attendance-summary", response_model=list[AttendanceCourseSummary]
)
def student_attendance_summary(
    student_id: int,
    period: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_student_academic_access(db, user, student_id)
    query = db.query(Enrollment).filter(Enrollment.student_id == student_id)
    if period:
        query = query.filter(Enrollment.period == period)
    return [
        AttendanceCourseSummary(
            section_id=item.section_id,
            section_code=item.section.code,
            subject_code=item.section.subject.code,
            subject_name=item.section.subject.description,
            present_count=sum(record.present for record in item.attendances),
            total_count=len(item.attendances),
            percentage=_percentage(
                sum(record.present for record in item.attendances), len(item.attendances)
            ),
        )
        for item in query.all()
    ]
