from sqlalchemy.orm import Session

from app.models.configuration_model import InstitutionSettings
from app.models.curriculum_model import CurriculumCourse
from app.models.enrollment_model import Enrollment
from app.models.section_model import Section
from app.models.student_model import Student
from app.schemas.enrollment_schema import EnrollmentCreate, EnrollmentUpdate
from app.services.enrollment_policy import selection_period
from app.services.governance_workflow import lock_governance


def create_enrollment(
    db: Session, enrollment_data: EnrollmentCreate, *, commit: bool = True
) -> Enrollment:
    lock_governance(db)
    selection_period(db, enrollment_data.section_id, enrollment_data.period, registration=True)
    settings = db.get(InstitutionSettings, 1)
    student = db.get(Student, enrollment_data.student_id)
    section = db.get(Section, enrollment_data.section_id)
    course = (
        db.query(CurriculumCourse)
        .filter_by(
            career_id=student.career_id,
            subject_id=section.subject_id,
            curriculum_version=student.curriculum_version,
        )
        .first()
    )
    new_enrollment = Enrollment(
        **enrollment_data.model_dump(),
        passing_grade=settings.passing_grade if settings else 70,
        curriculum_version=student.curriculum_version,
        curriculum_credits=course.credits if course else None,
    )

    db.add(new_enrollment)
    db.flush()
    if commit:
        db.commit()
        db.refresh(new_enrollment)

    return new_enrollment


def get_enrollments(db: Session) -> list[Enrollment]:
    return db.query(Enrollment).all()


def get_enrollment_by_id(db: Session, enrollment_id: int) -> Enrollment:
    return db.query(Enrollment).filter(Enrollment.enrollment_id == enrollment_id).first()


def update_enrollment(
    db: Session, enrollment_id: int, enrollment_data: EnrollmentUpdate, *, commit: bool = True
) -> Enrollment:

    lock_governance(db)
    enrollment = get_enrollment_by_id(db, enrollment_id)

    if not enrollment:
        return None

    update_data = enrollment_data.model_dump(exclude_unset=True)
    selection_period(
        db,
        update_data.get("section_id", enrollment.section_id),
        update_data.get("period", enrollment.period),
    )

    for key, value in update_data.items():
        setattr(enrollment, key, value)

    db.flush()
    if commit:
        db.commit()
        db.refresh(enrollment)

    return enrollment


def delete_enrollment(db: Session, enrollment_id: int, *, commit: bool = True) -> bool:
    enrollment = get_enrollment_by_id(db, enrollment_id)

    if not enrollment:
        return False

    db.delete(enrollment)
    db.flush()
    if commit:
        db.commit()

    return True
