from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import (
    ensure_enrollment_access,
    ensure_section_access,
    get_current_user,
    is_admin,
    require_permissions,
)
from app.db.Session import get_db
from app.models.attendance_model import Attendance, AttendanceChange
from app.models.enrollment_model import Enrollment
from app.models.user_model import User
from app.schemas.attendance_schema import (
    AttendanceBulkCreate,
    AttendanceCreate,
    AttendanceOut,
    AttendanceUpdate,
)
from app.services.attendance_workflow import change, day_record, snapshot, validate_day, write

router = APIRouter(prefix="/attendances", tags=["attendances"])
attendance_manager = require_permissions("grades.manage", fallback_roles=("admin", "teacher"))


def require_attendance_writer(db, user, enrollment_id):
    enrollment = ensure_enrollment_access(db, user, enrollment_id)
    if not is_admin(user) and (
        user.role.name.casefold() != "teacher" or user.teacher_id != enrollment.section.teacher_id
    ):
        raise HTTPException(403, "Solo el docente asignado o administración registra asistencia")
    return enrollment


@router.get("/sections/{section_id}/session")
def session(
    section_id: int,
    day: date = Query(default_factory=date.today),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    section = ensure_section_access(db, user, section_id)
    roster = []
    for enrollment in db.query(Enrollment).filter(
        Enrollment.section_id == section_id,
        Enrollment.state.in_(["enrolled", "completed", "failed"]),
    ):
        record = day_record(db, enrollment.enrollment_id, day)
        # Historic selections are only present for correcting an existing record.
        if enrollment.state != "enrolled" and record is None:
            continue
        roster.append(
            {
                "enrollment_id": enrollment.enrollment_id,
                "name": enrollment.student.full_name,
                "enrollment_number": enrollment.student.enrollment_number,
                "state": enrollment.state,
                "attendance_id": record.attendance_id if record else None,
                "status": record.status if record else None,
                "note": record.note if record else "",
                "excuse_reference": record.excuse_reference if record else "",
            }
        )
    return {
        "section_id": section_id,
        "section_code": section.code,
        "subject_name": section.subject_name,
        "teacher_name": section.teacher_name,
        "period_name": section.period_name,
        "days_of_week": section.days_of_week,
        "day": day,
        "roster": sorted(roster, key=lambda s: s["name"].casefold()),
    }


@router.post("/bulk", response_model=list[AttendanceOut])
def bulk(
    data: AttendanceBulkCreate,
    db: Session = Depends(get_db),
    user: User = Depends(attendance_manager),
):
    ensure_section_access(db, user, data.section_id)
    ids = [item.enrollment_id for item in data.records]
    if len(ids) != len(set(ids)):
        raise HTTPException(422, "No se repite un estudiante en el mismo pase de lista")
    enrollments = {
        e.enrollment_id: e
        for e in db.query(Enrollment).filter(
            Enrollment.section_id == data.section_id, Enrollment.enrollment_id.in_(ids)
        )
    }
    if len(enrollments) != len(ids):
        raise HTTPException(422, "Todos los estudiantes deben pertenecer a la sección")
    for enrollment in enrollments.values():
        require_attendance_writer(db, user, enrollment.enrollment_id)
        if "reason" not in data.model_fields_set and day_record(db, enrollment.enrollment_id, data.date):
            raise HTTPException(422, "Una corrección requiere un motivo explícito")
    saved = [
        write(
            db,
            user,
            enrollments[r.enrollment_id],
            data.date,
            r.present,
            r.status,
            r.note,
            r.excuse_reference,
            data.reason,
            data.exception_reason,
        )
        for r in data.records
    ]
    db.commit()
    return saved


@router.post("/", response_model=AttendanceOut)
def create(
    data: AttendanceCreate, db: Session = Depends(get_db), user: User = Depends(attendance_manager)
):
    enrollment = require_attendance_writer(db, user, data.enrollment_id)
    day = data.date.date() if data.date else date.today()
    if day_record(db, enrollment.enrollment_id, day):
        raise HTTPException(
            409, "Ya existe asistencia para ese estudiante y día; corrige el registro existente"
        )
    item = write(
        db,
        user,
        enrollment,
        day,
        data.present,
        data.status,
        data.note,
        data.excuse_reference,
        data.reason,
        data.exception_reason,
    )
    db.commit()
    return item


@router.get("/", response_model=list[AttendanceOut])
def list_attendances(
    enrollment_id: int | None = None,
    start: date | None = None,
    end: date | None = None,
    status: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if start and end and start > end:
        raise HTTPException(422, "El inicio debe ser anterior al fin")
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
    from sqlalchemy import func

    if start:
        query = query.filter(func.date(Attendance.date) >= start.isoformat())
    if end:
        query = query.filter(func.date(Attendance.date) <= end.isoformat())
    if status:
        query = query.filter(Attendance.status == status)
    return (
        query.order_by(Attendance.date.desc(), Attendance.attendance_id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/{attendance_id}/history")
def history(
    attendance_id: int, db: Session = Depends(get_db), user: User = Depends(attendance_manager)
):
    record = db.get(Attendance, attendance_id)
    changes = (
        db.query(AttendanceChange)
        .filter_by(attendance_id=attendance_id)
        .order_by(AttendanceChange.changed_at.desc(), AttendanceChange.change_id.desc())
        .all()
    )
    enrollment_id = (
        record.enrollment_id if record else changes[0].enrollment_id if changes else None
    )
    if not enrollment_id:
        raise HTTPException(404, "Registro no disponible")
    require_attendance_writer(db, user, enrollment_id)
    changes = [c for c in changes if c.enrollment_id == enrollment_id]
    return [
        {
            "change_id": c.change_id,
            "action": c.action,
            "reason": c.reason,
            "previous": c.previous,
            "current": c.current,
            "changed_by_name": c.changed_by_name,
            "changed_at": c.changed_at,
        }
        for c in changes
    ]


@router.get("/{attendance_id}", response_model=AttendanceOut)
def get_attendance(
    attendance_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    record = db.get(Attendance, attendance_id)
    if record is None:
        raise HTTPException(404, "Registro no disponible")
    ensure_enrollment_access(db, user, record.enrollment_id)
    return record


@router.patch("/{attendance_id}", response_model=AttendanceOut)
def update(
    attendance_id: int,
    data: AttendanceUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(attendance_manager),
):
    record = db.get(Attendance, attendance_id)
    if record is None:
        raise HTTPException(404, "Registro no disponible")
    enrollment = require_attendance_writer(db, user, record.enrollment_id)
    values = data.model_dump(exclude_unset=True)
    if any(values[k] is None for k in values if k not in {"exception_reason"}):
        raise HTTPException(422, "No se admiten campos nulos en la corrección")
    # A legacy boolean-only update must not be overridden by the previous status.
    state = data.status if "status" in values else None if "present" in values else record.status
    item = write(
        db,
        user,
        enrollment,
        data.date.date() if data.date else record.date.date(),
        data.present if "present" in values else record.present,
        state,
        data.note if "note" in values else record.note,
        data.excuse_reference if "excuse_reference" in values else record.excuse_reference,
        data.reason,
        data.exception_reason,
        record,
    )
    db.commit()
    return item


@router.delete("/{attendance_id}")
def delete(
    attendance_id: int,
    reason: str = Query(default="Eliminación de registro", min_length=2, max_length=250),
    db: Session = Depends(get_db),
    user: User = Depends(attendance_manager),
):
    record = db.get(Attendance, attendance_id)
    if record is None:
        raise HTTPException(404, "Registro no disponible")
    enrollment = require_attendance_writer(db, user, record.enrollment_id)
    validate_day(db, user, enrollment, record.date.date(), record)
    change(db, record, user, reason, snapshot(record), "deleted")
    db.delete(record)
    db.commit()
    return {"message": "Attendance deleted successfully"}
