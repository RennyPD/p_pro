"""Shortcuts for the fine-grained academic locks (Fase 3 G, finding B6).

Each resolves the section (and student) a record belongs to with a light
query, then calls ``lock_academic``. Those ids never change for an existing
record, so reading them before taking the lock is safe; everything the route
validates is read again after the lock (``lock_academic`` expires the session).
An unknown id only takes the shared general lock: the route answers 404.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assessment_model import Assessment
from app.models.attendance_model import Attendance
from app.models.enrollment_model import Enrollment
from app.models.grade_model import Grade
from app.models.operations_model import Assignment, Submission
from app.services.write_locks import lock_academic


def lock_sections(db: Session, *section_ids) -> None:
    lock_academic(db, sections=section_ids)


def _scalar(db: Session, statement):
    return db.execute(statement).scalar()


def lock_enrollment_section(db: Session, enrollment_id: int) -> None:
    section = _scalar(
        db, select(Enrollment.section_id).where(Enrollment.enrollment_id == enrollment_id)
    )
    lock_academic(db, sections=[section])


def lock_enrollment(db: Session, enrollment_id: int) -> None:
    """Section (capacity, waitlist) and student (credits, schedule) of a selection."""
    row = db.execute(
        select(Enrollment.section_id, Enrollment.student_id).where(
            Enrollment.enrollment_id == enrollment_id
        )
    ).first()
    lock_academic(db, sections=[row[0]] if row else [], students=[row[1]] if row else [])


def lock_selection(db: Session, section_ids, student_id: int | None) -> None:
    lock_academic(db, sections=section_ids, students=[student_id])


def lock_grade(db: Session, grade_id: int) -> None:
    section = _scalar(
        db,
        select(Enrollment.section_id)
        .join(Grade, Grade.enrollment_id == Enrollment.enrollment_id)
        .where(Grade.grade_id == grade_id),
    )
    lock_academic(db, sections=[section])


def lock_assessment(db: Session, assessment_id: int) -> None:
    section = _scalar(
        db, select(Assessment.section_id).where(Assessment.assessment_id == assessment_id)
    )
    lock_academic(db, sections=[section])


def lock_attendance(db: Session, attendance_id: int) -> None:
    section = _scalar(
        db,
        select(Enrollment.section_id)
        .join(Attendance, Attendance.enrollment_id == Enrollment.enrollment_id)
        .where(Attendance.attendance_id == attendance_id),
    )
    lock_academic(db, sections=[section])


def lock_assignment(db: Session, assignment_id: int) -> None:
    section = _scalar(
        db, select(Assignment.section_id).where(Assignment.assignment_id == assignment_id)
    )
    lock_academic(db, sections=[section])


def lock_submission(db: Session, submission_id: int) -> None:
    section = _scalar(
        db,
        select(Assignment.section_id)
        .join(Submission, Submission.assignment_id == Assignment.assignment_id)
        .where(Submission.submission_id == submission_id),
    )
    lock_academic(db, sections=[section])


def assignment_section(db: Session, assignment_id: int) -> int | None:
    return _scalar(
        db, select(Assignment.section_id).where(Assignment.assignment_id == assignment_id)
    )
