from sqlalchemy import case, func

from app.models.attendance_model import Attendance
from app.services.academic_grading import academic_result


def summarize_results(db, enrollments):
    active = [item for item in enrollments if item.state in {"enrolled", "completed", "failed"}]
    final = []
    provisional = []
    for enrollment in active:
        result = academic_result(db, enrollment)
        if result.value is not None:
            (final if result.final else provisional).append(result.value)
    attendance_count, present = (
        (
            db.query(
                func.count(Attendance.attendance_id),
                func.sum(case((Attendance.present.is_(True), 1), else_=0)),
            )
            .filter(Attendance.enrollment_id.in_([item.enrollment_id for item in active]))
            .one()
        )
        if active
        else (0, 0)
    )
    return {
        "average_grade": round(sum(final) / len(final), 2) if final else None,
        "final_grade_count": len(final),
        "provisional_average_grade": round(sum(provisional) / len(provisional), 2)
        if provisional
        else None,
        "provisional_grade_count": len(provisional),
        "attendance_percentage": round(present * 100 / attendance_count, 2)
        if attendance_count
        else None,
        "attendance_count": attendance_count,
    }
