"""School report cards and period reports (Fase 3, block F; decisions of 23/11/2026).

1. General MINERD-style format: one grade per subject and period (P1–P4),
   annual average, completivo, extraordinario, final grade and status, plus
   attendance per period, the homeroom teacher's remarks and the year result.
2. Families see a period's grade only once its result is final (every
   evaluation closed); periods still running show "En curso".
3. Remarks are written by the homeroom teacher (or academic staff) per period.

Grades come from the group's sections (block C) through the same calculation
as promotion, so the report card and the promotion proposal always agree.
"""

from collections import Counter

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.auth import ACADEMIC_SCOPE, has_permission, has_scope
from app.models.attendance_model import Attendance
from app.models.class_group_model import (
    ClassGroup,
    ClassGroupMember,
    RecoveryExam,
    ReportCardComment,
)
from app.models.configuration_model import AcademicPeriod, SchoolYear
from app.models.enrollment_model import Enrollment
from app.models.user_model import User
from app.services import class_groups as groups
from app.services.academic_grading import academic_result
from app.services.audit_log import record
from app.services.competencies import competency_groups, uses_competencies
from app.services.grading_scales import label
from app.services.institution_profile import settings_of

RESULT_LABELS = {
    "pending": "Pendiente",
    "promoted": "Promovido",
    "completivo": "Pendiente de completivo",
    "extraordinario": "Pendiente de extraordinario",
    "repeated": "Repite el grado",
}
STATUS_LABELS = {
    "passed": "Aprobada",
    "completivo": "Completivo",
    "extraordinario": "Extraordinario",
    "failed": "Reprobada",
    "incomplete": "En curso",
}


def member_for(db: Session, student_id: int, school_year_id: int | None) -> ClassGroupMember:
    query = (
        db.query(ClassGroupMember)
        .join(SchoolYear, SchoolYear.school_year_id == ClassGroupMember.school_year_id)
        .filter(ClassGroupMember.student_id == student_id)
    )
    if school_year_id is not None:
        query = query.filter(ClassGroupMember.school_year_id == school_year_id)
    member = query.order_by(SchoolYear.start_date.desc()).first()
    if member is None:
        raise HTTPException(404, "El estudiante no tiene grupo en ese año lectivo")
    return member


def has_school_card(db: Session, student_id: int) -> bool:
    return (
        db.query(ClassGroupMember.member_id)
        .filter(ClassGroupMember.student_id == student_id)
        .first()
        is not None
    )


def year_periods(db: Session, group: ClassGroup) -> list[AcademicPeriod]:
    return (
        db.query(AcademicPeriod)
        .filter_by(school_year_id=group.school_year_id)
        .order_by(AcademicPeriod.start_date)
        .all()
    )


def attendance_by_period(db: Session, group: ClassGroup, member, periods) -> list[dict]:
    sections = groups.group_sections(db, group)
    rows = []
    for period in periods:
        ids = [s.section_id for s in sections if s.period_id == period.period_id]
        counts: Counter = Counter()
        if ids:
            statuses = (
                db.query(Attendance.status)
                .join(Enrollment, Enrollment.enrollment_id == Attendance.enrollment_id)
                .filter(
                    Enrollment.student_id == member.student_id,
                    Enrollment.section_id.in_(ids),
                )
            )
            counts.update(status for (status,) in statuses)
        total = sum(counts.values())
        attended = counts["present"] + counts["late"] + counts["early_departure"]
        rows.append(
            {
                "period": period.name,
                "present": counts["present"],
                "late": counts["late"],
                "absent": counts["absent"],
                "excused": counts["excused"],
                "total": total,
                "percentage": round(attended * 100 / total, 1) if total else None,
            }
        )
    return rows


def final_value(subject) -> float | None:
    if subject.especial is not None and subject.status == "passed":
        return subject.especial
    if subject.extraordinario is not None:
        return subject.extraordinario
    if subject.completivo is not None:
        return subject.completivo
    return subject.average if subject.complete else None


MONTHS = ("Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sept", "Oct", "Nov", "Dic")


def months_label(period) -> str:
    """ "Ago–Sept–Oct" for a period from August to October (signature lines)."""
    labels, year, month = [], period.start_date.year, period.start_date.month
    while (year, month) <= (period.end_date.year, period.end_date.month) and len(labels) < 6:
        labels.append(MONTHS[month - 1])
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return "–".join(labels)


def order_number(group: ClassGroup, member: ClassGroupMember) -> int:
    """Número de orden: alphabetical position by surname within the group."""
    ordered = sorted(
        groups.active_members(group) or [member],
        key=lambda m: (m.student.last_name.casefold(), m.student.first_name.casefold()),
    )
    ids = [m.member_id for m in ordered]
    return ids.index(member.member_id) + 1 if member.member_id in ids else len(ids) + 1


def competency_grades(db: Session, group, member, scale, periods, courses, subjects):
    """Per subject: one row per competency group with its P1–P4 labels.

    A period's competency grades show only when that period's result is final,
    like every other grade on the card (decision 2 of block F).
    """
    groups_rows = competency_groups(db)
    sections = groups.group_sections(db, group)
    result = {}
    for course, subject in zip(courses, subjects):
        rows = {g.competency_group_id: [None] * len(periods) for g in groups_rows}
        for index, period in enumerate(periods):
            if subject.periods[index] is None:
                continue
            section = next(
                (
                    s
                    for s in sections
                    if s.subject_id == course.subject_id and s.period_id == period.period_id
                ),
                None,
            )
            if section is None:
                continue
            enrollment = (
                db.query(Enrollment)
                .filter_by(student_id=member.student_id, section_id=section.section_id)
                .first()
            )
            if enrollment is None:
                continue
            for grade in enrollment.grades:
                assessment = grade.assessment
                if (
                    grade.status == "published"
                    and assessment is not None
                    and assessment.competency_group_id in rows
                ):
                    rows[assessment.competency_group_id][index] = label(scale, grade.grade_value)
        result[course.subject_id] = [rows[g.competency_group_id] for g in groups_rows]
    return result


def build_report_card(db: Session, member: ClassGroupMember) -> dict:
    group = member.class_group
    scale = groups.group_scale(db, group)
    periods = year_periods(db, group)
    courses = groups.curriculum(db, group)
    subjects = groups.subject_results(
        db, group, member, scale, periods, courses, groups.group_sections(db, group)
    )
    comments = {
        c.period_id: c for c in db.query(ReportCardComment).filter_by(member_id=member.member_id)
    }
    settings = settings_of(db)
    teacher = group.homeroom_teacher
    student = member.student
    official = uses_competencies(group.career)
    exams = {
        (exam.subject_id, exam.kind): exam
        for exam in db.query(RecoveryExam).filter_by(member_id=member.member_id)
    }
    competencies = (
        competency_grades(db, group, member, scale, periods, courses, subjects) if official else {}
    )
    return {
        "format": "minerd_secondary" if official else "general",
        "first_name": student.first_name,
        "last_name": student.last_name,
        "sigerd_id": student.sigerd_id or "",
        "order_number": order_number(group, member),
        "shift": group.shift or "",
        "section_name": group.name,
        "competency_groups": [g.name for g in competency_groups(db)] if official else [],
        "student_id": student.student_id,
        "student_name": student.full_name,
        "enrollment_number": student.enrollment_number,
        "member_id": member.member_id,
        "member_status": member.status,
        "institution": {
            "name": settings.institution_name if settings else "Nexo Académico",
            "school_code": settings.school_code if settings else "",
            "regional": settings.regional if settings else "",
            "district": settings.district if settings else "",
            "phone": settings.school_phone if settings else "",
            "province": settings.province if settings else "",
            "municipality": settings.municipality if settings else "",
        },
        "class_group_id": group.class_group_id,
        "group_label": group.label,
        "career_name": group.career.name,
        "grade_number": group.grade_number,
        "school_year": group.school_year.name,
        "homeroom_teacher": f"{teacher.first_name} {teacher.last_name}" if teacher else None,
        "scale_name": scale.name,
        "passing_grade": float(scale.passing_value),
        "periods": [
            {
                "period_id": p.period_id,
                "name": p.name,
                "short": f"P{index}",
                "closed": p.status == "closed",
                "months": months_label(p),
            }
            for index, p in enumerate(periods, start=1)
        ],
        "subjects": [
            {
                "subject_id": s.subject_id,
                "code": s.code,
                "name": s.name,
                "periods": [
                    label(scale, value) if value is not None else None for value in s.periods
                ],
                "average": s.average,
                "average_label": s.average_label,
                "completivo": label(scale, s.completivo) if s.completivo is not None else None,
                "extraordinario": label(scale, s.extraordinario)
                if s.extraordinario is not None
                else None,
                "final": label(scale, final_value(s)) if final_value(s) is not None else None,
                "especial": label(scale, s.especial) if s.especial is not None else None,
                "status": s.status,
                "status_label": STATUS_LABELS.get(s.status, s.status),
                # Situación final en la asignatura: A (aprobado) / R (reprobado).
                "situation": "A" if s.passed else "R" if s.passed is False else None,
                "competencies": competencies.get(s.subject_id, []),
                "recovery": {
                    kind: {
                        "average": float(exam.annual_average),
                        "exam": float(exam.exam_grade),
                        "final": float(exam.final_grade),
                        "passed": exam.passed,
                    }
                    for (subject_id, kind), exam in exams.items()
                    if subject_id == s.subject_id
                },
            }
            for s in subjects
        ],
        "attendance": attendance_by_period(db, group, member, periods),
        "comments": [
            {
                "period_id": p.period_id,
                "period": p.name,
                "comment": comments[p.period_id].comment,
            }
            for p in periods
            if p.period_id in comments
        ],
        "weights": {
            "completivo": float(scale.completivo_average_weight),
            "extraordinario": float(scale.extraordinario_average_weight),
        },
        "result_note": member.result_note or "",
        "result": member.result if member.result_confirmed_at else "pending",
        "result_label": RESULT_LABELS.get(
            member.result if member.result_confirmed_at else "pending", member.result
        ),
    }


# --- Access ------------------------------------------------------------------


def teaches_group(db: Session, user: User, group: ClassGroup) -> bool:
    return (
        user.teacher_id is not None
        and groups.visible_groups(db, user)
        .filter(ClassGroup.class_group_id == group.class_group_id)
        .first()
        is not None
    )


def can_comment(db: Session, user: User, group: ClassGroup) -> bool:
    if user.teacher_id is not None and user.teacher_id == group.homeroom_teacher_id:
        return True
    return has_scope(user, *ACADEMIC_SCOPE) and has_permission(user, "grades.manage")


def save_comment(db: Session, user: User, group, member, period_id: int, text: str) -> None:
    if not can_comment(db, user, group):
        raise HTTPException(
            403, "Solo el titular del grupo o la coordinación escriben observaciones"
        )
    period = db.get(AcademicPeriod, period_id)
    if period is None or period.school_year_id != group.school_year_id:
        raise HTTPException(404, "El período no pertenece al año lectivo del grupo")
    text = text.strip()
    existing = (
        db.query(ReportCardComment)
        .filter_by(member_id=member.member_id, period_id=period_id)
        .first()
    )
    before = existing.comment if existing else None
    if not text:
        if existing is None:
            return
        db.delete(existing)
    else:
        if existing is None:
            existing = ReportCardComment(member_id=member.member_id, period_id=period_id)
            db.add(existing)
        existing.comment = text
        existing.author_id = user.user_id
        existing.updated_at = groups.now()
    record(
        db,
        user,
        "report_card.comment",
        f"class-group:{group.class_group_id}",
        f"{member.student.full_name}, {period.name}: «{before or '—'}» → «{text or '—'}»",
    )


# --- Period report and promotion summary --------------------------------------


def period_report(db: Session, group: ClassGroup, period_id: int) -> dict:
    period = db.get(AcademicPeriod, period_id)
    if period is None or period.school_year_id != group.school_year_id:
        raise HTTPException(404, "El período no pertenece al año lectivo del grupo")
    scale = groups.group_scale(db, group)
    passing = float(scale.passing_value)
    courses = groups.curriculum(db, group)
    sections = {
        s.subject_id: s for s in groups.group_sections(db, group) if s.period_id == period_id
    }
    rows, values_by_subject = [], {c.subject_id: [] for c in courses}
    for member in sorted(groups.active_members(group), key=lambda m: m.student.last_name):
        grades, below = [], []
        for course in courses:
            section = sections.get(course.subject_id)
            enrollment = (
                db.query(Enrollment)
                .filter_by(student_id=member.student_id, section_id=section.section_id)
                .first()
                if section
                else None
            )
            outcome = academic_result(db, enrollment) if enrollment else None
            value = outcome.value if outcome else None
            final = bool(outcome and outcome.final)
            if value is not None:
                values_by_subject[course.subject_id].append(value)
                if value < passing:
                    below.append(course.subject.code)
            grades.append(
                {
                    "subject_id": course.subject_id,
                    "value": value,
                    "label": label(scale, value) if value is not None else None,
                    "final": final,
                }
            )
        attendance = attendance_by_period(db, group, member, [period])[0]
        rows.append(
            {
                "member_id": member.member_id,
                "student_name": member.student.full_name,
                "enrollment_number": member.student.enrollment_number,
                "grades": grades,
                "below_passing": below,
                "attendance": attendance["percentage"],
            }
        )
    subjects = []
    for course in courses:
        values = values_by_subject[course.subject_id]
        subjects.append(
            {
                "subject_id": course.subject_id,
                "code": course.subject.code,
                "name": course.subject.description,
                "average": round(sum(values) / len(values), 2) if values else None,
                "passed_percentage": round(
                    sum(1 for v in values if v >= passing) * 100 / len(values), 1
                )
                if values
                else None,
                "graded": len(values),
            }
        )
    return {
        "class_group_id": group.class_group_id,
        "group_label": group.label,
        "period_id": period.period_id,
        "period": period.name,
        "closed": period.status == "closed",
        "passing_grade": passing,
        "subjects": subjects,
        "students": rows,
    }


def promotion_summary(db: Session, user: User, school_year_id: int) -> list[dict]:
    result = []
    query = (
        groups.visible_groups(db, user)
        .filter(ClassGroup.school_year_id == school_year_id)
        .order_by(ClassGroup.career_id, ClassGroup.grade_number, ClassGroup.name)
    )
    for group in query:
        counts = Counter(
            (m.result if m.result_confirmed_at else "pending") for m in groups.active_members(group)
        )
        result.append(
            {
                "class_group_id": group.class_group_id,
                "label": group.label,
                "career_name": group.career.name,
                "grade_number": group.grade_number,
                "students": sum(counts.values()),
                "promoted": counts["promoted"],
                "completivo": counts["completivo"],
                "extraordinario": counts["extraordinario"],
                "repeated": counts["repeated"],
                "pending": counts["pending"],
            }
        )
    return result
