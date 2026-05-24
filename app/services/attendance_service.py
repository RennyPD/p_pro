from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.repositories.attendance_repository import (
    create_attendance,
    get_attendances,
    get_attendance_by_id,
    update_attendance,
    delete_attendance
)

from app.schemas.attendance_schema import AttendanceCreate, AttendanceUpdate

def create_attendance_service(db: Session, attendance_data: AttendanceCreate):
    return create_attendance(db, attendance_data)

def get_attendances_service(db: Session):
    return get_attendances(db)

def get_attendance_by_id_service(db: Session, attendance_id: int):
    attendance = get_attendance_by_id(db, attendance_id)

    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="attendance not found"
        )

    return attendance

def update_attendance_service(db: Session, attendance_id: int, attendance_data: AttendanceUpdate):
    attendance = update_attendance(db, attendance_id, attendance_data)

    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="attendance not found"
        )

    return attendance

def delete_attendance_service(db: Session, attendance_id: int):
    attendance = delete_attendance(db, attendance_id)

    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="attendance not found"
        )

    return {"message": "attendance deleted successfully"}