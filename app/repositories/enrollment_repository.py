from sqlalchemy.orm import Session

from app.models.configuration_model import InstitutionSettings
from app.models.enrollment_model import Enrollment
from app.schemas.enrollment_schema import EnrollmentCreate, EnrollmentUpdate
from app.services.enrollment_policy import selection_period
from app.services.governance_workflow import lock_governance


def create_enrollment(
    db: Session, enrollment_data: EnrollmentCreate, *, commit: bool = True
) -> Enrollment:
    lock_governance(db)
    selection_period(db, enrollment_data.section_id, enrollment_data.period, registration=True)
    settings = db.get(InstitutionSettings, 1)
    new_enrollment = Enrollment(
        **enrollment_data.model_dump(), passing_grade=settings.passing_grade if settings else 70
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
