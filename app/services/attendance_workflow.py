from datetime import datetime, time, timedelta

from fastapi import HTTPException

from app.auth import has_scope
from app.enums.dayEnum import DAY_ORDER
from app.models.attendance_model import Attendance, AttendanceChange
from app.models.configuration_model import AcademicPeriod
from app.services.business_time import business_date
from app.services.effective_schedule import effective_blocks

STATUSES = {"present", "absent", "late", "excused", "early_departure"}


def status_values(present, status):
    if status is None and present is None:
        raise HTTPException(
            422, "Selecciona un estado; sin registrar no equivale a presente o ausente"
        )
    status = status or ("present" if present else "absent")
    if status not in STATUSES:
        raise HTTPException(422, "Estado de asistencia no válido")
    return status in {"present", "late", "early_departure"}, status


def day_record(db, enrollment_id, day):
    return (
        db.query(Attendance)
        .filter(
            Attendance.enrollment_id == enrollment_id,
            Attendance.date >= datetime.combine(day, time.min),
            Attendance.date < datetime.combine(day + timedelta(days=1), time.min),
        )
        .first()
    )


def validate_day(db, user, enrollment, day, existing=None, exception_reason=None):
    section = enrollment.section
    if section.status in {"closed", "cancelled"}:
        raise HTTPException(409, "La sección está cerrada o cancelada")
    if enrollment.state != "enrolled" and not (
        existing and enrollment.state in {"completed", "failed"}
    ):
        raise HTTPException(409, "Solo se registra asistencia nueva para selecciones activas")
    if day > business_date():
        raise HTTPException(422, "No se registra asistencia de fechas futuras")
    periods = (
        db.query(AcademicPeriod)
        .filter(AcademicPeriod.name.in_({section.period_name, enrollment.period} - {""}))
        .all()
    )
    for period in periods:
        if period.status == "closed":
            raise HTTPException(409, "El período está cerrado; requiere reapertura administrativa")
        if not period.start_date <= day <= period.end_date:
            raise HTTPException(422, "La fecha debe estar dentro del período académico")
    # Historical entries are not reinterpreted: their unchanged day may be corrected.
    if existing and existing.date.date() == day:
        return
    if not any(
        DAY_ORDER[block.day_of_week] == day.weekday() for block in effective_blocks(section)
    ):
        if not (has_scope(user, "attendance.manage") and exception_reason):
            raise HTTPException(
                422,
                "No es un día de clase de la sección. Una sesión extraordinaria exige excepción administrativa con motivo",
            )


def snapshot(item):
    return {
        "date": item.date.isoformat(),
        "status": item.status,
        "present": item.present,
        "note": item.note,
        "excuse_reference": item.excuse_reference,
    }


def change(db, item, user, reason, previous, action="updated"):
    current = None if action == "deleted" else snapshot(item)
    if current == previous:
        return
    db.add(
        AttendanceChange(
            attendance_id=item.attendance_id,
            enrollment_id=item.enrollment_id,
            changed_by=user.user_id,
            changed_by_name=user.username,
            reason=reason[:250],
            previous=previous,
            current=current,
            action=action,
        )
    )


def write(
    db,
    user,
    enrollment,
    day,
    present,
    status,
    note,
    reference,
    reason,
    exception_reason=None,
    existing=None,
):
    item = existing or day_record(db, enrollment.enrollment_id, day)
    validate_day(db, user, enrollment, day, item, exception_reason)
    values = status_values(present, status)
    if values[1] == "excused" and not (note.strip() or reference.strip()):
        raise HTTPException(422, "Una ausencia justificada requiere observación o referencia")
    previous = snapshot(item) if item else None
    if item is None:
        item = Attendance(
            enrollment_id=enrollment.enrollment_id, date=datetime.combine(day, time.min)
        )
        db.add(item)
    item.present, item.status = values
    item.note, item.excuse_reference = note, reference
    if existing and existing.date.date() != day:
        conflict = day_record(db, enrollment.enrollment_id, day)
        if conflict and conflict.attendance_id != existing.attendance_id:
            raise HTTPException(409, "Ya existe asistencia para ese estudiante y día")
        item.date = datetime.combine(day, time.min)
    db.flush()
    change(
        db,
        item,
        user,
        reason + (f" · Excepción: {exception_reason}" if exception_reason else ""),
        previous,
        "created" if previous is None else "updated",
    )
    return item
