from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import ensure_enrollment_access, get_current_user, is_admin
from app.db.Session import get_db
from app.models.attendance_model import Attendance
from app.models.enrollment_model import Enrollment
from app.models.user_model import User
from app.schemas.attendance_schema import AttendanceCreate, AttendanceOut, AttendanceUpdate

router = APIRouter(prefix="/attendances", tags=["attendances"])


def require_attendance_writer(db: Session, user: User, enrollment_id: int):
    enrollment = ensure_enrollment_access(db, user, enrollment_id)
    if not is_admin(user) and user.teacher_id != enrollment.section.teacher_id:
        raise HTTPException(
            status_code=403, detail="Only the assigned teacher or an admin can record attendance"
        )
    return enrollment


@router.post("/", response_model=AttendanceOut)
def create_attendance(
    data: AttendanceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_attendance_writer(db, user, data.enrollment_id)
    values = data.model_dump(exclude_none=True)
    attendance = Attendance(**values)
    db.add(attendance)
    db.commit()
    db.refresh(attendance)
    return attendance


@router.get("/", response_model=list[AttendanceOut])
def list_attendances(
    enrollment_id: int | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Attendance)
    if enrollment_id is not None:
        ensure_enrollment_access(db, user, enrollment_id)
        query = query.filter(Attendance.enrollment_id == enrollment_id)
    elif not is_admin(user):
        if user.student_id is not None:
            query = query.join(Attendance.enrollment).filter_by(student_id=user.student_id)
        elif user.teacher_id is not None:
            query = (
                query.join(Attendance.enrollment)
                .join(Enrollment.section)
                .filter_by(teacher_id=user.teacher_id)
            )
        else:
            return []
    return query.offset(skip).limit(limit).all()


@router.get("/{attendance_id}", response_model=AttendanceOut)
def get_attendance(
    attendance_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    attendance = db.get(Attendance, attendance_id)
    if attendance is None:
        raise HTTPException(status_code=404, detail="Attendance not found")
    ensure_enrollment_access(db, user, attendance.enrollment_id)
    return attendance


@router.patch("/{attendance_id}", response_model=AttendanceOut)
def update_attendance(
    attendance_id: int,
    data: AttendanceUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    attendance = db.get(Attendance, attendance_id)
    if attendance is None:
        raise HTTPException(status_code=404, detail="Attendance not found")
    require_attendance_writer(db, user, attendance.enrollment_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(attendance, key, value)
    db.commit()
    db.refresh(attendance)
    return attendance


@router.delete("/{attendance_id}")
def delete_attendance(
    attendance_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    attendance = db.get(Attendance, attendance_id)
    if attendance is None:
        raise HTTPException(status_code=404, detail="Attendance not found")
    require_attendance_writer(db, user, attendance.enrollment_id)
    db.delete(attendance)
    db.commit()
    return {"message": "Attendance deleted successfully"}
