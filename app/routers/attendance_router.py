from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.Session import get_db
from app.services.attendance_service import (
    create_attendance_service,
    get_attendances_service,
    get_attendance_by_id_service,
    update_attendance_service,
    delete_attendance_service
)
from app.schemas.attendance_schema import (
    AttendanceCreate,
    AttendanceUpdate,
    AttendanceOut
)

router = APIRouter(prefix="/attendances",
                    tags=["attendance"])

@router.post("/", response_model=AttendanceOut)
def create_attendance(
    attendance_data: AttendanceCreate,
    db: Session = Depends(get_db)
):
    return create_attendance_service(db, attendance_data)

@router.get("/", response_model=list[AttendanceOut])
def get_attendances(
    db: Session = Depends(get_db)
):
    return get_attendances_service(db)

@router.get("/{attendance_id}", response_model=AttendanceOut)
def get_attendance_by_id(
    attendance_id: int,
    db: Session = Depends(get_db)
):
    return get_attendance_by_id_service(db, attendance_id)

@router.put("/{attendance_id}", response_model=AttendanceOut)
def update_attendance(
    attendance_id: int,
    attendance_data: AttendanceUpdate,
    db: Session = Depends(get_db)
):
    return update_attendance_service(db, attendance_id, attendance_data)

@router.delete("/{attendance_id}")
def delete_attendance(
    attendance_id: int,
    db: Session = Depends(get_db)
):
    return delete_attendance_service(db, attendance_id)
