"""Fixed school groups: members, subjects per period, promotion and re-enrollment.

Fase 3, block C (decisions of 23/11/2026):

1. A group's subjects are regular sections, one per subject of the grade and
   period of the year, so every existing workflow applies to them.
2. Promotion is proposed from the annual average of each subject (the mean of
   its period results) against the institution's passing grade, and confirmed
   by a person. Block D refines completivo and extraordinario.
3. A financial hold blocks joining a group, as it blocks any enrollment, unless
   someone with ``finance.supervise`` records an exception with its reason.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, time
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.auth import ACADEMIC_SCOPE, has_permission, has_scope
from app.models.career_model import Career
from app.models.class_group_model import (
    ClassGroup,
    ClassGroupMember,
    ClassGroupSubject,
    RecoveryExam,
)
from app.models.configuration_model import AcademicPeriod, SchoolYear
from app.models.curriculum_model import CurriculumCourse
from app.models.enrollment_model import Enrollment
from app.models.section_model import Section
from app.models.student_model import Student
from app.models.teacher_model import Teacher
from app.models.user_model import User
from app.services.academic_grading import academic_result
from app.services.audit_log import record
from app.services.business_time import business_date
from app.services.grading_scales import label, passing_for, scale_for_career
from app.services.institution_profile import is_school_level

# Group subjects start without a timetable; times are placeholders until the
# schedule editor assigns real blocks (no days means no clashes are checked).
PLACEHOLDER_START = time(7, 30)
PLACEHOLDER_END = time(8, 15)
OPEN = "enrolled"


def now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


# --- Scope -----------------------------------------------------------------


def visible_groups(db: Session, user: User):
    """Groups the account may see: all with academic reach, a teacher's own, else none."""
    query = db.query(ClassGroup)
    if has_scope(user, *ACADEMIC_SCOPE):
        return query
    if user.teacher_id is None:
        return query.filter(False)
    taught = db.query(Section.class_group_id).filter(
        Section.teacher_id == user.teacher_id, Section.class_group_id.is_not(None)
    )
    return query.filter(
        (ClassGroup.homeroom_teacher_id == user.teacher_id) | ClassGroup.class_group_id.in_(taught)
    )


def ensure_group_access(db: Session, user: User, class_group_id: int) -> ClassGroup:
    group = db.get(ClassGroup, class_group_id)
    if group is None:
        raise HTTPException(404, "Grupo no encontrado")
    if not visible_groups(db, user).filter(ClassGroup.class_group_id == class_group_id).first():
        raise HTTPException(403, "El grupo está fuera de tu ámbito académico")
    return group


def group_or_404(db: Session, class_group_id: int) -> ClassGroup:
    group = db.get(ClassGroup, class_group_id)
    if group is None:
        raise HTTPException(404, "Grupo no encontrado")
    return group


# --- Groups ----------------------------------------------------------------


def validate_group(db: Session, career_id: int, grade_number: int, school_year_id: int) -> None:
    career = db.get(Career, career_id)
    if career is None:
        raise HTTPException(404, "Programa no encontrado")
    if not is_school_level(career.academic_level):
        raise HTTPException(
            409, "Los grupos fijos son para programas de nivel inicial, primario o secundario"
        )
    if not 1 <= grade_number <= career.duration_terms:
        raise HTTPException(
            422, f"El grado debe estar entre 1 y {career.duration_terms} para {career.name}"
        )
    if db.get(SchoolYear, school_year_id) is None:
        raise HTTPException(404, "Año lectivo no encontrado")


def validate_teacher(db: Session, teacher_id: int | None) -> None:
    if teacher_id is None:
        return
    teacher = db.get(Teacher, teacher_id)
    if teacher is None or not teacher.active:
        raise HTTPException(409, "El docente no existe o no está activo")


def ensure_unique_group(db: Session, values: dict, current: ClassGroup | None = None) -> None:
    other = (
        db.query(ClassGroup)
        .filter_by(
            career_id=values["career_id"],
            grade_number=values["grade_number"],
            name=values["name"],
            school_year_id=values["school_year_id"],
        )
        .first()
    )
    if other is not None and other is not current:
        raise HTTPException(409, "Ya existe ese grupo en el mismo grado y año lectivo")


def curriculum(db: Session, group: ClassGroup) -> list[CurriculumCourse]:
    career = group.career
    return (
        db.query(CurriculumCourse)
        .filter_by(
            career_id=career.career_id,
            term_number=group.grade_number,
            curriculum_version=career.curriculum_version,
        )
        .order_by(CurriculumCourse.curriculum_course_id)
        .all()
    )


def teacher_for(group: ClassGroup, subject_id: int) -> int | None:
    for item in group.subject_teachers:
        if item.subject_id == subject_id:
            return item.teacher_id
    return group.homeroom_teacher_id


def open_periods(db: Session, group: ClassGroup) -> list[AcademicPeriod]:
    return (
        db.query(AcademicPeriod)
        .filter(
            AcademicPeriod.school_year_id == group.school_year_id,
            AcademicPeriod.status != "closed",
        )
        .order_by(AcademicPeriod.start_date)
        .all()
    )


def group_sections(db: Session, group: ClassGroup, periods=None) -> list[Section]:
    query = db.query(Section).filter(Section.class_group_id == group.class_group_id)
    if periods is not None:
        query = query.filter(Section.period_id.in_([p.period_id for p in periods]))
    return query.all()


def active_members(group: ClassGroup) -> list[ClassGroupMember]:
    return [member for member in group.members if member.status == OPEN]


def assign_subject_teacher(db: Session, group: ClassGroup, subject_id: int, teacher_id: int):
    """Set who teaches a subject; open-period sections of the group follow."""
    if subject_id not in {course.subject_id for course in curriculum(db, group)}:
        raise HTTPException(409, "La asignatura no pertenece al plan de este grado")
    validate_teacher(db, teacher_id)
    current = next((i for i in group.subject_teachers if i.subject_id == subject_id), None)
    if current is None:
        group.subject_teachers.append(
            ClassGroupSubject(subject_id=subject_id, teacher_id=teacher_id)
        )
    else:
        current.teacher_id = teacher_id
    moved = 0
    for section in group_sections(db, group, open_periods(db, group)):
        if section.subject_id == subject_id and section.teacher_id != teacher_id:
            section.teacher_id = teacher_id
            moved += 1
    db.flush()
    return moved


# --- Subjects per period ---------------------------------------------------


def section_code(group: ClassGroup, subject, period: AcademicPeriod) -> str:
    year = group.school_year.name.replace(" ", "")
    return f"{subject.code}-{group.grade_number}{group.name}-{year}-P{period.sequence}"[:100]


def enroll_in_section(db: Session, student: Student, section: Section, course) -> bool:
    exists = (
        db.query(Enrollment.enrollment_id)
        .filter_by(student_id=student.student_id, section_id=section.section_id)
        .first()
    )
    if exists:
        enrollment = db.get(Enrollment, exists[0])
        if enrollment.state == "withdrawn":
            enrollment.state = "enrolled"
            return True
        return False
    db.add(
        Enrollment(
            student_id=student.student_id,
            section_id=section.section_id,
            academic_period=section.academic_period,
            state="enrolled",
            passing_grade=passing_for(db, student),
            curriculum_version=student.curriculum_version,
            curriculum_credits=course.credits if course else None,
        )
    )
    return True


def generate_subjects(db: Session, group: ClassGroup) -> dict:
    """One section per subject of the grade and open period; members enrolled in each."""
    periods = open_periods(db, group)
    if not periods:
        raise HTTPException(409, "El año lectivo no tiene períodos abiertos; genéralos primero")
    courses = curriculum(db, group)
    if not courses:
        raise HTTPException(
            409, f"El plan de estudios no tiene asignaturas para el grado {group.grade_number}"
        )
    missing = [c.subject.code for c in courses if teacher_for(group, c.subject_id) is None]
    if missing:
        raise HTTPException(
            409,
            "Asigna un docente titular o un docente a: " + ", ".join(sorted(missing)),
        )
    existing = {(s.subject_id, s.period_id) for s in group_sections(db, group, periods)}
    created = 0
    for period in periods:
        for course in courses:
            if (course.subject_id, period.period_id) in existing:
                continue
            code = section_code(group, course.subject, period)
            if db.query(Section.section_id).filter_by(code=code).first():
                raise HTTPException(409, f"Ya existe la sección {code}")
            section = Section(
                code=code,
                description=f"{course.subject.description} · {group.grade_number}.º {group.name}",
                teacher_id=teacher_for(group, course.subject_id),
                subject_id=course.subject_id,
                days_of_week="",
                start_time=PLACEHOLDER_START,
                end_time=PLACEHOLDER_END,
                capacity=max(group.capacity, len(active_members(group)), 1),
                room=group.room,
                modality="in_person",
                status="active",
                minimum_capacity=1,
                academic_period=period,
                class_group_id=group.class_group_id,
            )
            db.add(section)
            created += 1
    db.flush()
    enrolled = sync_member_enrollments(db, group)
    return {"sections_created": created, "enrollments_created": enrolled}


def sync_member_enrollments(db: Session, group: ClassGroup, members=None) -> int:
    """Enroll members in the group's sections of open periods (idempotent)."""
    courses = {course.subject_id: course for course in curriculum(db, group)}
    sections = group_sections(db, group, open_periods(db, group))
    created = 0
    for member in members if members is not None else active_members(group):
        for section in sections:
            created += enroll_in_section(
                db, member.student, section, courses.get(section.subject_id)
            )
    db.flush()
    return created


def withdraw_open_enrollments(db: Session, group: ClassGroup, student_id: int) -> int:
    sections = [s.section_id for s in group_sections(db, group, open_periods(db, group))]
    if not sections:
        return 0
    rows = (
        db.query(Enrollment)
        .filter(
            Enrollment.student_id == student_id,
            Enrollment.section_id.in_(sections),
            Enrollment.state.in_(("enrolled", "waitlisted")),
        )
        .all()
    )
    for enrollment in rows:
        enrollment.state = "withdrawn"
        enrollment.waitlist_position = None
    return len(rows)


# --- Members ---------------------------------------------------------------


def hold_problem(student: Student) -> str | None:
    if student.academic_hold:
        return "tiene un bloqueo académico activo"
    if student.financial_hold:
        return "tiene un bloqueo financiero activo"
    return None


def check_holds(student: Student, actor: User, override_reason: str | None) -> str | None:
    """None when the student may join; the financial exception is returned for the audit."""
    if student.academic_hold:
        raise HTTPException(409, f"{student.full_name} tiene un bloqueo académico activo")
    if not student.financial_hold:
        return None
    reason = (override_reason or "").strip()
    if not reason:
        raise HTTPException(409, f"{student.full_name} tiene un bloqueo financiero activo")
    if not has_permission(actor, "finance.supervise"):
        raise HTTPException(
            403, "Solo finanzas puede autorizar una excepción al bloqueo financiero"
        )
    if len(reason) < 5:
        raise HTTPException(422, "Explica el motivo de la excepción financiera")
    return reason


def add_member(
    db: Session,
    group: ClassGroup,
    student: Student,
    actor: User,
    override_reason: str | None = None,
    *,
    change_program: bool = False,
) -> ClassGroupMember:
    if group.status != "active":
        raise HTTPException(409, "El grupo está cerrado")
    if not student.active:
        raise HTTPException(409, f"{student.full_name} está inactivo")
    if student.career_id != group.career_id and not change_program:
        raise HTTPException(
            409, f"{student.full_name} no pertenece al programa {group.career.name}"
        )
    exception = check_holds(student, actor, override_reason)
    taken = (
        db.query(ClassGroupMember)
        .filter_by(student_id=student.student_id, school_year_id=group.school_year_id)
        .first()
    )
    if taken is not None:
        raise HTTPException(
            409, f"{student.full_name} ya está en {taken.class_group.label} este año lectivo"
        )
    if len(active_members(group)) >= group.capacity:
        raise HTTPException(409, "El grupo no tiene cupo disponible")
    if student.career_id != group.career_id:
        record(
            db,
            actor,
            "student.program_changed",
            f"student:{student.student_id}",
            f"Programa {student.career_id} → {group.career_id} por reinscripción",
        )
        student.career_id = group.career_id
        student.assigned_curriculum_version = None
    member = ClassGroupMember(
        student=student,
        school_year_id=group.school_year_id,
        status=OPEN,
        joined_on=business_date(),
        result="pending",
    )
    group.members.append(member)
    db.flush()
    sync_member_enrollments(db, group, [member])
    detail = f"{student.full_name} → {group.label}"
    if exception:
        detail += f"; excepción al bloqueo financiero: {exception}"
    record(db, actor, "class_group.member_added", f"class-group:{group.class_group_id}", detail)
    return member


def member_or_404(group: ClassGroup, member_id: int) -> ClassGroupMember:
    member = next((m for m in group.members if m.member_id == member_id), None)
    if member is None:
        raise HTTPException(404, "El estudiante no está en este grupo")
    return member


def withdraw_member(db: Session, group: ClassGroup, member: ClassGroupMember, actor, reason):
    if member.status != OPEN:
        raise HTTPException(409, "El estudiante ya no está activo en el grupo")
    withdrawn = withdraw_open_enrollments(db, group, member.student_id)
    member.status = "withdrawn"
    member.left_on = business_date()
    record(
        db,
        actor,
        "class_group.member_withdrawn",
        f"class-group:{group.class_group_id}",
        f"{member.student.full_name}: {reason}; {withdrawn} materias retiradas",
    )


def transfer_member(
    db: Session, group: ClassGroup, member: ClassGroupMember, target: ClassGroup, actor, reason
):
    if member.status != OPEN:
        raise HTTPException(409, "El estudiante ya no está activo en el grupo")
    if target.class_group_id == group.class_group_id:
        raise HTTPException(409, "Elige un grupo distinto")
    if target.school_year_id != group.school_year_id or target.career_id != group.career_id:
        raise HTTPException(409, "El traslado es entre grupos del mismo programa y año lectivo")
    if target.status != "active":
        raise HTTPException(409, "El grupo de destino está cerrado")
    if len(active_members(target)) >= target.capacity:
        raise HTTPException(409, "El grupo de destino no tiene cupo disponible")
    withdraw_open_enrollments(db, group, member.student_id)
    member.class_group = target
    db.flush()
    sync_member_enrollments(db, target, [member])
    detail = f"{member.student.full_name}: {group.label} → {target.label}; {reason}"
    for resource in (group.class_group_id, target.class_group_id):
        record(db, actor, "class_group.member_transferred", f"class-group:{resource}", detail)


# --- Promotion -------------------------------------------------------------

RECOVERY_KINDS = ("completivo", "extraordinario")


@dataclass
class SubjectResult:
    subject_id: int
    code: str
    name: str
    periods: list[float | None] = field(default_factory=list)
    average: float | None = None
    average_label: str | None = None
    complete: bool = False
    passed: bool | None = None
    # passed | completivo | extraordinario | failed | incomplete
    status: str = "incomplete"
    completivo: float | None = None
    extraordinario: float | None = None


def group_scale(db: Session, group: ClassGroup):
    return scale_for_career(db, group.career)


def subject_results(db: Session, group: ClassGroup, member, scale, periods, courses, sections):
    exams = {
        (exam.subject_id, exam.kind): exam
        for exam in db.query(RecoveryExam).filter_by(member_id=member.member_id)
    }
    passing = float(scale.passing_value)
    results = []
    for course in courses:
        result = SubjectResult(course.subject_id, course.subject.code, course.subject.description)
        complete = True
        for period in periods:
            section = next(
                (
                    s
                    for s in sections
                    if s.subject_id == course.subject_id and s.period_id == period.period_id
                ),
                None,
            )
            enrollment = (
                db.query(Enrollment)
                .filter_by(student_id=member.student_id, section_id=section.section_id)
                .first()
                if section
                else None
            )
            outcome = academic_result(db, enrollment) if enrollment else None
            value = outcome.value if outcome and outcome.final else None
            complete = complete and value is not None
            result.periods.append(value)
        values = [v for v in result.periods if v is not None]
        result.complete = complete and bool(values)
        if values:
            result.average = round(sum(values) / len(values), 2)
            result.average_label = label(scale, result.average)
        completivo = exams.get((course.subject_id, "completivo"))
        extraordinario = exams.get((course.subject_id, "extraordinario"))
        result.completivo = float(completivo.final_grade) if completivo else None
        result.extraordinario = float(extraordinario.final_grade) if extraordinario else None
        if not result.complete:
            result.status = "incomplete"
        elif result.average >= passing:
            result.status = "passed"
        elif completivo is None:
            result.status = "completivo"
        elif completivo.passed:
            result.status = "passed"
        elif extraordinario is None:
            result.status = "extraordinario"
        else:
            result.status = "passed" if extraordinario.passed else "failed"
        if result.complete:
            result.passed = result.status == "passed"
        results.append(result)
    return results


def proposal_for(subjects: list[SubjectResult]) -> str | None:
    statuses = {s.status for s in subjects}
    if not subjects or "incomplete" in statuses:
        return None
    for status, proposal in (
        ("failed", "repeated"),
        ("extraordinario", "extraordinario"),
        ("completivo", "completivo"),
    ):
        if status in statuses:
            return proposal
    return "promoted"


def promotion_proposal(db: Session, group: ClassGroup) -> dict:
    scale = group_scale(db, group)
    periods = (
        db.query(AcademicPeriod)
        .filter_by(school_year_id=group.school_year_id)
        .order_by(AcademicPeriod.start_date)
        .all()
    )
    courses = curriculum(db, group)
    sections = group_sections(db, group)
    rows = []
    for member in sorted(active_members(group), key=lambda m: m.student.last_name):
        subjects = subject_results(db, group, member, scale, periods, courses, sections)
        proposal = proposal_for(subjects)
        rows.append(
            {
                "member_id": member.member_id,
                "student_id": member.student_id,
                "student_name": member.student.full_name,
                "enrollment_number": member.student.enrollment_number,
                "subjects": [vars(s) for s in subjects],
                "failed": [s.code for s in subjects if s.passed is False],
                "complete": proposal is not None,
                "proposal": proposal,
                "result": member.result,
                "confirmed": member.result_confirmed_at is not None,
            }
        )
    return {
        "class_group_id": group.class_group_id,
        "passing_grade": float(scale.passing_value),
        "scale_name": scale.name,
        "completivo_average_weight": float(scale.completivo_average_weight),
        "extraordinario_average_weight": float(scale.extraordinario_average_weight),
        "periods": [p.name for p in periods],
        "members": rows,
    }


def record_recovery(
    db: Session, group: ClassGroup, member, subject_id: int, kind: str, exam_grade, actor
) -> RecoveryExam:
    """Grade a completivo or extraordinario: weighted with the annual average."""
    if member.status != OPEN:
        raise HTTPException(409, "El estudiante ya no está activo en el grupo")
    scale = group_scale(db, group)
    periods = (
        db.query(AcademicPeriod)
        .filter_by(school_year_id=group.school_year_id)
        .order_by(AcademicPeriod.start_date)
        .all()
    )
    courses = [c for c in curriculum(db, group) if c.subject_id == subject_id]
    if not courses:
        raise HTTPException(409, "La asignatura no pertenece al plan de este grado")
    subject = subject_results(
        db, group, member, scale, periods, courses, group_sections(db, group)
    )[0]
    existing = (
        db.query(RecoveryExam)
        .filter_by(member_id=member.member_id, subject_id=subject_id, kind=kind)
        .first()
    )
    allowed = subject.status == kind or (existing is not None and subject.status != "incomplete")
    if not subject.complete:
        raise HTTPException(409, "La materia aún no tiene todas sus notas finales")
    if not allowed:
        message = (
            "La materia ya está aprobada"
            if subject.status == "passed"
            else "Primero registra el completivo"
            if kind == "extraordinario"
            else "El completivo ya está registrado; corrige ese examen o registra el extraordinario"
        )
        raise HTTPException(409, message)
    if kind == "extraordinario":
        later = None
    else:
        later = (
            db.query(RecoveryExam.recovery_exam_id)
            .filter_by(member_id=member.member_id, subject_id=subject_id, kind="extraordinario")
            .first()
        )
    if later:
        raise HTTPException(409, "Ya hay un extraordinario; el completivo no se puede cambiar")
    weight = (
        scale.completivo_average_weight
        if kind == "completivo"
        else scale.extraordinario_average_weight
    )
    average = Decimal(str(subject.average))
    exam = Decimal(str(exam_grade))
    final = ((average * weight + exam * (Decimal(100) - weight)) / Decimal(100)).quantize(
        Decimal("0.01"), ROUND_HALF_UP
    )
    passed = final >= scale.passing_value
    before = None
    if existing is None:
        existing = RecoveryExam(member_id=member.member_id, subject_id=subject_id, kind=kind)
        db.add(existing)
    else:
        before = f"{existing.exam_grade} → "
    existing.annual_average = average
    existing.exam_grade = exam
    existing.final_grade = final
    existing.passed = passed
    existing.recorded_by = actor.user_id if actor else None
    existing.recorded_at = now()
    db.flush()
    record(
        db,
        actor,
        "class_group.recovery_recorded",
        f"class-group:{group.class_group_id}",
        f"{member.student.full_name}, {subject.code}: {kind} {before or ''}{exam}; "
        f"promedio {average} ({weight} %) → {final} " + ("aprobada" if passed else "reprobada"),
    )
    return existing


def confirm_results(db: Session, group: ClassGroup, decisions, actor) -> int:
    members = {m.member_id: m for m in active_members(group)}
    changed = 0
    for decision in decisions:
        member = members.get(decision.member_id)
        if member is None:
            raise HTTPException(404, "El estudiante no está activo en este grupo")
        note = (decision.note or "").strip() or None
        if member.result == decision.result and member.result_confirmed_at and not note:
            continue
        record(
            db,
            actor,
            "class_group.result_confirmed",
            f"class-group:{group.class_group_id}",
            f"{member.student.full_name}: {member.result} → {decision.result}"
            + (f"; {note}" if note else ""),
        )
        member.result = decision.result
        member.result_note = note
        member.result_confirmed_at = now()
        changed += 1
    return changed


# --- Re-enrollment ---------------------------------------------------------


def expected_target(group: ClassGroup, member: ClassGroupMember) -> tuple[int, int | None]:
    """(grade, career or None for any next program) a confirmed result leads to."""
    if member.result == "repeated":
        return group.grade_number, group.career_id
    if group.grade_number >= group.career.duration_terms:
        return 1, None  # last grade: first grade of the next program
    return group.grade_number + 1, group.career_id


def reinscribe(
    db: Session,
    group: ClassGroup,
    target: ClassGroup,
    member_ids: list[int],
    actor: User,
    override_reason: str | None,
) -> dict:
    if target.school_year.start_date <= group.school_year.start_date:
        raise HTTPException(409, "El grupo de destino debe ser de un año lectivo posterior")
    members = {m.member_id: m for m in active_members(group)}
    done, blocked = [], []
    for member_id in member_ids:
        member = members.get(member_id)
        if member is None:
            raise HTTPException(404, "El estudiante no está activo en este grupo")
        name = member.student.full_name
        if member.result_confirmed_at is None or member.result not in {"promoted", "repeated"}:
            blocked.append({"student_name": name, "reason": "Resultado sin confirmar o completivo"})
            continue
        grade, career = expected_target(group, member)
        if target.grade_number != grade or (career is not None and target.career_id != career):
            blocked.append(
                {
                    "student_name": name,
                    "reason": f"Le corresponde el grado {grade}, no {target.label}",
                }
            )
            continue
        problem = hold_problem(member.student)
        if problem and not (
            member.student.financial_hold
            and not member.student.academic_hold
            and override_reason
            and has_permission(actor, "finance.supervise")
        ):
            blocked.append({"student_name": name, "reason": problem.capitalize()})
            continue
        try:
            add_member(
                db,
                target,
                member.student,
                actor,
                override_reason if member.student.financial_hold else None,
                change_program=career is None,
            )
        except HTTPException as exc:
            blocked.append({"student_name": name, "reason": exc.detail})
            continue
        done.append(name)
    return {"reinscribed": done, "blocked": blocked}
