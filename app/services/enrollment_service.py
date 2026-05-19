from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.repositories.enrollment_repository import (
    create_enrollment,
    get_enrollments,
    get_enrollment_by_id,
    update_enrollment,
    delete_enrollment
)

from app.schemas.enrollment_schema import EnrollmentCreate, EnrollmentUpdate

def create_enrollment_service(db: Session, enrollment_data: EnrollmentCreate):
    return create_enrollment(db, enrollment_data)

def get_enrollments_service(db: Session):
    return get_enrollments(db)

def get_enrollment_by_id_service(db: Session, enrollment_id: int):
    enrollment = get_enrollment_by_id(db, enrollment_id)

    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enrollment not found"
        )

    return enrollment

def update_enrollment_service(db: Session, enrollment_id: int, enrollment_data: EnrollmentUpdate):
    enrollment = update_enrollment(db, enrollment_id, enrollment_data)

    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enrollment not found"
        )

    return enrollment

def delete_enrollment_service(db: Session, enrollment_id: int):
    enrollment = delete_enrollment(db, enrollment_id)

    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enrollment not found"
        )

    return {"message": "Enrollment deleted successfully"}