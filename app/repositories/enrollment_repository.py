from sqlalchemy.orm import Session

from app.models.configuration_model import InstitutionSettings
from app.models.enrollment_model import Enrollment
from app.schemas.enrollment_schema import EnrollmentCreate, EnrollmentUpdate
from app.services.governance_workflow import lock_governance


def create_enrollment(db: Session, enrollment_data: EnrollmentCreate) -> Enrollment:
    lock_governance(db)
    settings = db.get(InstitutionSettings, 1)
    new_enrollment = Enrollment(
        **enrollment_data.model_dump(), passing_grade=settings.passing_grade if settings else 70
    )

    db.add(new_enrollment)
    db.commit()
    db.refresh(new_enrollment)

    return new_enrollment


def get_enrollments(db: Session) -> list[Enrollment]:
    return db.query(Enrollment).all()


def get_enrollment_by_id(db: Session, enrollment_id: int) -> Enrollment:
    return db.query(Enrollment).filter(Enrollment.enrollment_id == enrollment_id).first()


def update_enrollment(
    db: Session, enrollment_id: int, enrollment_data: EnrollmentUpdate
) -> Enrollment:

    enrollment = get_enrollment_by_id(db, enrollment_id)

    if not enrollment:
        return None

    update_data = enrollment_data.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(enrollment, key, value)

    db.commit()
    db.refresh(enrollment)

    return enrollment


def delete_enrollment(db: Session, enrollment_id: int) -> bool:
    enrollment = get_enrollment_by_id(db, enrollment_id)

    if not enrollment:
        return False

    db.delete(enrollment)
    db.commit()

    return True
