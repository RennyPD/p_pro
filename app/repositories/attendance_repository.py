from sqlalchemy.orm import Session
from app.models.attendance_model import Attendance
from app.schemas.attendance_schema import AttendanceCreate, AttendanceUpdate

def create_attendance(db: Session, attendance_data: AttendanceCreate) -> Attendance:

    new_attendance = Attendance(**attendance_data.model_dump())

    db.add(new_attendance)
    db.commit()
    db.refresh(new_attendance)

    return new_attendance

def get_attendances(db: Session) -> list[Attendance]:
    return db.query(Attendance).all()

def get_attendance_by_id(db: Session, attendance_id: int) -> Attendance:
    return db.query(Attendance).filter(Attendance.attendance_id == attendance_id).first()

def update_attendance(db: Session, attendance_id: int, attendance_data: AttendanceUpdate) -> Attendance:

    attendance = get_attendance_by_id(db, attendance_id)

    if not attendance:
        return None
    
    update_data = attendance_data.model_dump(
        exclude_unset=True
    )

    for key, value in update_data.items():
        setattr(attendance, key, value)

    db.commit()
    db.refresh(attendance)

    return attendance

def delete_attendance(db: Session, attendance_id: int) -> bool:
    attendance = get_attendance_by_id(db, attendance_id)

    if not attendance:
        return False

    db.delete(attendance)
    db.commit()

    return True