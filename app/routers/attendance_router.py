from datetime import datetime, time

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import ensure_enrollment_access, ensure_section_access, get_current_user, is_admin
from app.db.Session import get_db
from app.models.attendance_model import Attendance
from app.models.enrollment_model import Enrollment
from app.models.user_model import User
from app.schemas.attendance_schema import (
    AttendanceBulkCreate,
    AttendanceCreate,
    AttendanceOut,
    AttendanceUpdate,
)

router = APIRouter(prefix="/attendances", tags=["attendances"])


@router.post("/bulk", response_model=list[AttendanceOut])
def save_section_attendance(
    data: AttendanceBulkCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_section_access(db, user, data.section_id)
    enrollment_ids = {item.enrollment_id for item in data.records}
    enrollments = (
        db.query(Enrollment)
        .filter(
            Enrollment.section_id == data.section_id,
            Enrollment.enrollment_id.in_(enrollment_ids),
        )
        .all()
    )
    if len(enrollments) != len(enrollment_ids):
        raise HTTPException(
            status_code=422, detail="Every attendance record must belong to the section"
        )
    day_start = datetime.combine(data.date, time.min)
    day_end = datetime.combine(data.date, time.max)
    saved = []
    for item in data.records:
        attendance = (
            db.query(Attendance)
            .filter(
                Attendance.enrollment_id == item.enrollment_id,
                Attendance.date >= day_start,
                Attendance.date <= day_end,
            )
            .first()
        )
        if attendance is None:
            attendance = Attendance(enrollment_id=item.enrollment_id, date=day_start)
            db.add(attendance)
        attendance.present = item.present
        saved.append(attendance)
    db.commit()
    for attendance in saved:
        db.refresh(attendance)
    return saved


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
