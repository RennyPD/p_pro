from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.Session import get_db
from app.services.enrollment_service import (
    create_enrollment_service,
    get_enrollments_service,
    get_enrollment_by_id_service,
    update_enrollment_service,
    delete_enrollment_service
)
from app.schemas.enrollment_schema import (
    EnrollmentCreate,
    EnrollmentUpdate,
    EnrollmentOut
)

router = APIRouter(prefix="/enrollments",
                    tags=["enrollment"])

@router.post("/", response_model=EnrollmentOut)
def create_enrollment(
    enrollment_data: EnrollmentCreate,
    db: Session = Depends(get_db)
):
    return create_enrollment_service(db, enrollment_data)

@router.get("/", response_model=list[EnrollmentOut])
def get_enrollments(
    db: Session = Depends(get_db)
):
    return get_enrollments_service(db)

@router.get("/{enrollment_id}", response_model=EnrollmentOut)
def get_enrollment_by_id(
    enrollment_id: int,
    db: Session = Depends(get_db)
):
    return get_enrollment_by_id_service(db, enrollment_id)

@router.put("/{enrollment_id}", response_model=EnrollmentOut)
def update_enrollment(
    enrollment_id: int,
    enrollment_data: EnrollmentUpdate,
    db: Session = Depends(get_db)
):
    return update_enrollment_service(db, enrollment_id, enrollment_data)

@router.delete("/{enrollment_id}")
def delete_enrollment(
    enrollment_id: int,
    db: Session = Depends(get_db)
):
    return delete_enrollment_service(db, enrollment_id)
