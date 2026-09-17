from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.configuration_model import InstitutionSettings
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
        passing_grade = (db.get(InstitutionSettings, 1) or InstitutionSettings()).passing_grade
        average = (
            sum(prerequisite_grades) / len(prerequisite_grades) if prerequisite_grades else None
        )
        if average is None or average < passing_grade:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Prerequisite {curriculum_course.prerequisite.code} is not completed",
            )
    current = (
        db.query(Enrollment)
        .filter(
            Enrollment.student_id == enrollment_data.student_id,
            Enrollment.period == enrollment_data.period,
            Enrollment.state == "enrolled",
        )
        .all()
    )
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
    enrollment = update_enrollment(db, enrollment_id, enrollment_data)

    if not enrollment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment not found")

    return enrollment


def delete_enrollment_service(db: Session, enrollment_id: int):
    enrollment = delete_enrollment(db, enrollment_id)

    if not enrollment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment not found")

    return {"message": "Enrollment deleted successfully"}
