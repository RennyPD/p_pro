from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.configuration_model import AcademicPeriod, InstitutionSettings
from app.models.curriculum_model import CurriculumCourse
from app.models.enrollment_model import Enrollment
from app.models.section_model import Section
from app.models.student_model import Student
from app.repositories.enrollment_repository import (
    create_enrollment,
    delete_enrollment,
    get_enrollment_by_id,
    get_enrollments,
    update_enrollment,
)
from app.schemas.enrollment_schema import EnrollmentCreate, EnrollmentUpdate


def create_enrollment_service(db: Session, enrollment_data: EnrollmentCreate):
    requested_section = db.get(Section, enrollment_data.section_id)
    if requested_section is None:
        raise HTTPException(status_code=404, detail="Section not found")
    student = db.get(Student, enrollment_data.student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")
    if not student.active:
        raise HTTPException(status_code=409, detail="Inactive students cannot enroll")
    if student.academic_hold or student.financial_hold:
        reasons = []
        if student.academic_hold:
            reasons.append("academic")
        if student.financial_hold:
            reasons.append("financial")
        raise HTTPException(
            status_code=409,
            detail=f"Student has an active {' and '.join(reasons)} hold",
        )
    period = db.query(AcademicPeriod).filter(AcademicPeriod.name == enrollment_data.period).first()
    today = date.today()
    if period:
        if period.status == "closed":
            raise HTTPException(status_code=409, detail="The academic period is closed")
        if period.registration_start and today < period.registration_start:
            raise HTTPException(status_code=409, detail="Registration has not started")
        if period.registration_end and today > period.registration_end:
            raise HTTPException(status_code=409, detail="Registration is closed")
    curriculum_course = (
        db.query(CurriculumCourse)
        .filter(
            CurriculumCourse.career_id == student.career_id,
            CurriculumCourse.subject_id == requested_section.subject_id,
        )
        .first()
    )
    if curriculum_course and curriculum_course.prerequisite_subject_id:
        prerequisite_grades = [
            grade.grade_value
            for enrollment in student.enrollments
            if enrollment.section.subject_id == curriculum_course.prerequisite_subject_id
            for grade in enrollment.grades
        ]
        settings = db.get(InstitutionSettings, 1)
        passing_grade = settings.passing_grade if settings else 70.0
        average = (
            sum(prerequisite_grades) / len(prerequisite_grades) if prerequisite_grades else None
        )
        if average is None or average < passing_grade:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Prerequisite {curriculum_course.prerequisite.code} is not completed",
            )
    settings = db.get(InstitutionSettings, 1)
    passing_grade = settings.passing_grade if settings else 70.0
    same_subject_grades = [
        grade.grade_value
        for enrollment in student.enrollments
        if enrollment.section.subject_id == requested_section.subject_id
        for grade in enrollment.grades
    ]
    if same_subject_grades and sum(same_subject_grades) / len(same_subject_grades) >= passing_grade:
        raise HTTPException(status_code=409, detail="The subject is already completed")
    current = (
        db.query(Enrollment)
        .filter(
            Enrollment.student_id == enrollment_data.student_id,
            Enrollment.period == enrollment_data.period,
            Enrollment.state == "enrolled",
        )
        .all()
    )
    max_credits = settings.max_credits_per_period if settings else 24
    current_credits = 0.0
    for enrollment in current:
        course = (
            db.query(CurriculumCourse)
            .filter(
                CurriculumCourse.career_id == student.career_id,
                CurriculumCourse.subject_id == enrollment.section.subject_id,
            )
            .first()
        )
        current_credits += course.credits if course else 0
    requested_credits = curriculum_course.credits if curriculum_course else 0
    if current_credits + requested_credits > max_credits:
        raise HTTPException(status_code=409, detail="Maximum credit load exceeded")

    enrolled_count = (
        db.query(Enrollment)
        .filter(
            Enrollment.section_id == requested_section.section_id,
            Enrollment.period == enrollment_data.period,
            Enrollment.state == "enrolled",
        )
        .count()
    )
    if enrolled_count >= requested_section.capacity:
        waitlist_count = (
            db.query(Enrollment)
            .filter(
                Enrollment.section_id == requested_section.section_id,
                Enrollment.period == enrollment_data.period,
                Enrollment.state == "waitlisted",
            )
            .count()
        )
        enrollment_data = enrollment_data.model_copy(
            update={"state": "waitlisted", "waitlist_position": waitlist_count + 1}
        )
        return create_enrollment(db, enrollment_data)
    requested_days = set(requested_section.days_of_week.split(", "))
    for enrollment in current:
        section = enrollment.section
        same_day = requested_days.intersection(section.days_of_week.split(", "))
        overlaps = (
            requested_section.start_time < section.end_time
            and section.start_time < requested_section.end_time
        )
        if same_day and overlaps:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Schedule conflict with section {section.code}",
            )
    return create_enrollment(db, enrollment_data)


def get_enrollments_service(db: Session):
    return get_enrollments(db)


def get_enrollment_by_id_service(db: Session, enrollment_id: int):
    enrollment = get_enrollment_by_id(db, enrollment_id)

    if not enrollment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment not found")

    return enrollment


def update_enrollment_service(db: Session, enrollment_id: int, enrollment_data: EnrollmentUpdate):
    current = get_enrollment_by_id(db, enrollment_id)
    if not current:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment not found")
    if enrollment_data.state == "withdrawn":
        period = db.query(AcademicPeriod).filter(AcademicPeriod.name == current.period).first()
        if period and period.withdrawal_deadline and date.today() > period.withdrawal_deadline:
            raise HTTPException(status_code=409, detail="The withdrawal deadline has passed")
    enrollment = update_enrollment(db, enrollment_id, enrollment_data)

    if not enrollment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment not found")

    if enrollment.state == "withdrawn":
        next_waiting = (
            db.query(Enrollment)
            .filter(
                Enrollment.section_id == enrollment.section_id,
                Enrollment.period == enrollment.period,
                Enrollment.state == "waitlisted",
            )
            .order_by(Enrollment.waitlist_position, Enrollment.enrollment_date)
            .first()
        )
        if next_waiting:
            next_waiting.state = "enrolled"
            next_waiting.waitlist_position = None
            db.commit()

    return enrollment


def delete_enrollment_service(db: Session, enrollment_id: int):
    enrollment = delete_enrollment(db, enrollment_id)

    if not enrollment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment not found")

    return {"message": "Enrollment deleted successfully"}
