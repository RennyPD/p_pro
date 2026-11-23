"""Billing plans: recurring charges (monthly tuition, per-period fees).

A plan charges a fixed amount to the active students of some careers (or school
grades), plus individually added students and minus exclusions. Every cycle is
a calendar month written "YYYY-MM". Generating a cycle is idempotent: the unique
(account, plan, cycle) constraint on charges and the finance lock make a second
run, or two simultaneous runs, charge nobody twice.
"""

import calendar
from datetime import date

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.career_model import Career
from app.models.class_group_model import ClassGroup, ClassGroupMember
from app.models.configuration_model import AcademicPeriod, SchoolYear
from app.models.finance_model import (
    BillingConcept,
    BillingPlan,
    BillingPlanTarget,
    BillingRun,
    Charge,
    StudentAccount,
)
from app.models.student_model import Student
from app.models.user_model import User
from app.schemas.finance_schema import (
    BillingPlanCreate,
    BillingPlanOut,
    BillingPlanTargets,
    BillingPlanUpdate,
    BillingPreview,
    BillingPreviewStudent,
    GradeTarget,
)
from app.services.finance_workflow import (
    business_date,
    cents,
    event,
    get_account,
    lock_finance,
    money,
)
from app.services.institution_profile import is_school_level

MONTHS = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)
PREVIEW_LIMIT = 200


def parse_cycle(cycle: str) -> date:
    year, month = cycle.split("-")
    return date(int(year), int(month), 1)


def cycle_key(month: date) -> str:
    return f"{month.year:04d}-{month.month:02d}"


def cycle_label(cycle: str) -> str:
    month = parse_cycle(cycle)
    return f"{MONTHS[month.month - 1]} {month.year}"


def last_day(month: date) -> date:
    return month.replace(day=calendar.monthrange(month.year, month.month)[1])


def plan_cycles(plan: BillingPlan) -> list[str]:
    cycles, month = [], plan.start_month
    end = plan.start_month if plan.frequency == "single" else plan.end_month
    while month <= end:
        cycles.append(cycle_key(month))
        month = date(month.year + month.month // 12, month.month % 12 + 1, 1)
    return cycles


def due_date(plan: BillingPlan, cycle: str) -> date:
    month = parse_cycle(cycle)
    return month.replace(day=min(plan.due_day, last_day(month).day))


def targets_of(plan: BillingPlan) -> BillingPlanTargets:
    return BillingPlanTargets(
        career_ids=sorted(t.career_id for t in plan.targets if t.kind == "career"),
        grades=[
            GradeTarget(career_id=t.career_id, grade_number=t.grade_number)
            for t in sorted(
                (t for t in plan.targets if t.kind == "grade"),
                key=lambda t: (t.career_id, t.grade_number),
            )
        ],
        student_ids=sorted(t.student_id for t in plan.targets if t.kind == "student"),
        excluded_student_ids=sorted(t.student_id for t in plan.targets if t.kind == "exclude"),
    )


def generated_cycles(db: Session, plan: BillingPlan) -> list[str]:
    rows = db.query(BillingRun.cycle).filter_by(billing_plan_id=plan.billing_plan_id).distinct()
    return sorted(row[0] for row in rows)


def plan_out(db: Session, plan: BillingPlan) -> BillingPlanOut:
    cycles = plan_cycles(plan)
    done = generated_cycles(db, plan)
    pending = [cycle for cycle in cycles if cycle not in done]
    return BillingPlanOut(
        billing_plan_id=plan.billing_plan_id,
        name=plan.name,
        charge_description=plan.charge_description,
        billing_concept_id=plan.billing_concept_id,
        amount=plan.amount,
        frequency=plan.frequency,
        start_month=cycle_key(plan.start_month),
        end_month=cycle_key(plan.end_month),
        due_day=plan.due_day,
        period_id=plan.period_id,
        active=plan.active,
        targets=targets_of(plan),
        school_year_id=plan.school_year_id,
        sibling_discount=plan.sibling_discount,
        cycles=cycles,
        generated_cycles=done,
        next_cycle=pending[0] if pending and plan.active else None,
    )


def set_targets(db: Session, plan: BillingPlan, targets: BillingPlanTargets) -> None:
    careers = set(targets.career_ids)
    students = set(targets.student_ids) | set(targets.excluded_student_ids)
    if careers and db.query(Career).filter(Career.career_id.in_(careers)).count() != len(careers):
        raise HTTPException(422, "Alguna carrera o grado seleccionado no existe")
    if students and (
        db.query(Student).filter(Student.student_id.in_(students)).count() != len(students)
    ):
        raise HTTPException(422, "Algún estudiante seleccionado no existe")
    if set(targets.student_ids) & set(targets.excluded_student_ids):
        raise HTTPException(422, "Un estudiante no puede estar incluido y excluido a la vez")
    grades = sorted({(g.career_id, g.grade_number) for g in targets.grades})
    if grades and plan.school_year_id is None:
        raise HTTPException(422, "Para cobrar por grado, elige el año lectivo del plan")
    for career_id, grade in grades:
        career = db.get(Career, career_id)
        if career is None or not is_school_level(career.academic_level):
            raise HTTPException(422, "Los grados son de programas de nivel escolar")
        if grade > career.duration_terms:
            raise HTTPException(422, f"{career.name} no tiene el grado {grade}")
    plan.targets.clear()
    db.flush()
    plan.targets.extend(
        [BillingPlanTarget(kind="career", career_id=item) for item in sorted(careers)]
        + [
            BillingPlanTarget(kind="grade", career_id=career_id, grade_number=grade)
            for career_id, grade in grades
        ]
        + [BillingPlanTarget(kind="student", student_id=item) for item in targets.student_ids]
        + [
            BillingPlanTarget(kind="exclude", student_id=item)
            for item in targets.excluded_student_ids
        ]
    )


def ensure_unique_name(db: Session, name: str, plan_id: int | None = None) -> None:
    query = db.query(BillingPlan).filter(BillingPlan.name == name)
    if plan_id is not None:
        query = query.filter(BillingPlan.billing_plan_id != plan_id)
    if query.first() is not None:
        raise HTTPException(409, "Ya existe un plan de cobro con ese nombre")


def ensure_months(plan: BillingPlan) -> None:
    if plan.frequency == "single":
        plan.end_month = plan.start_month
    if plan.end_month < plan.start_month:
        raise HTTPException(422, "El mes final no puede ser anterior al mes inicial")
    if len(plan_cycles(plan)) > 36:
        raise HTTPException(422, "Un plan puede abarcar como máximo 36 meses")


def create_plan(db: Session, data: BillingPlanCreate, user: User) -> BillingPlan:
    lock_finance(db)
    ensure_unique_name(db, data.name)
    if (
        data.billing_concept_id is not None
        and db.get(BillingConcept, data.billing_concept_id) is None
    ):
        raise HTTPException(422, "El concepto de cobro no existe")
    if data.period_id is not None and db.get(AcademicPeriod, data.period_id) is None:
        raise HTTPException(422, "El período académico no existe")
    year = db.get(SchoolYear, data.school_year_id) if data.school_year_id else None
    if data.school_year_id is not None and year is None:
        raise HTTPException(422, "El año lectivo no existe")
    start = data.start_month or (cycle_key(year.start_date) if year else None)
    if start is None:
        raise HTTPException(422, "Indica el mes inicial o el año lectivo del plan")
    end = data.end_month or (
        cycle_key(year.end_date) if year and data.frequency == "monthly" else start
    )
    plan = BillingPlan(
        name=data.name,
        charge_description=data.charge_description,
        billing_concept_id=data.billing_concept_id,
        amount=money(cents(data.amount)),
        frequency=data.frequency,
        start_month=parse_cycle(start),
        end_month=parse_cycle(end),
        due_day=data.due_day,
        period_id=data.period_id,
        school_year_id=data.school_year_id,
        sibling_discount=data.sibling_discount,
        active=True,
        created_by=user.user_id,
    )
    ensure_months(plan)
    db.add(plan)
    db.flush()
    set_targets(db, plan, data.targets)
    event(
        db,
        user,
        None,
        "billing_plan.created",
        {
            "billing_plan_id": plan.billing_plan_id,
            "name": plan.name,
            "amount_cents": cents(plan.amount),
            "frequency": plan.frequency,
            "cycles": plan_cycles(plan),
            "targets": data.targets.model_dump(),
        },
    )
    return plan


def get_plan(db: Session, plan_id: int) -> BillingPlan:
    plan = db.get(BillingPlan, plan_id)
    if plan is None:
        raise HTTPException(404, "Plan de cobro no encontrado")
    return plan


def update_plan(db: Session, plan: BillingPlan, data: BillingPlanUpdate, user: User) -> None:
    """Changes apply to cycles not generated yet; charges already posted keep their amount."""
    lock_finance(db)
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    before = {key: str(getattr(plan, key)) for key in changes if key != "end_month"}
    if "name" in changes:
        ensure_unique_name(db, changes["name"], plan.billing_plan_id)
    if "amount" in changes:
        changes["amount"] = money(cents(changes["amount"]))
    if "end_month" in changes:
        before["end_month"] = cycle_key(plan.end_month)
        changes["end_month"] = parse_cycle(changes["end_month"])
        done = generated_cycles(db, plan)
        if done and cycle_key(changes["end_month"]) < done[-1]:
            raise HTTPException(409, "El mes final no puede quedar antes de un ciclo ya generado")
    for key, value in changes.items():
        setattr(plan, key, value)
    ensure_months(plan)
    event(
        db,
        user,
        None,
        "billing_plan.updated",
        {"billing_plan_id": plan.billing_plan_id, "before": before, "after": changes},
    )


def replace_targets(db: Session, plan: BillingPlan, targets: BillingPlanTargets, user: User):
    lock_finance(db)
    before = targets_of(plan).model_dump()
    set_targets(db, plan, targets)
    event(
        db,
        user,
        None,
        "billing_plan.targets_updated",
        {"billing_plan_id": plan.billing_plan_id, "before": before, "after": targets.model_dump()},
    )


def ensure_cycle(plan: BillingPlan, cycle: str) -> None:
    if cycle not in plan_cycles(plan):
        raise HTTPException(422, "Ese mes está fuera de las fechas del plan")


def eligible_students(db: Session, plan: BillingPlan, cycle: str) -> list[Student]:
    """Active students the plan applies to; those admitted after the cycle are left out."""
    targets = targets_of(plan)
    excluded = set(targets.excluded_student_ids)
    query = db.query(Student).filter(Student.active.is_(True))
    if not targets.career_ids and not targets.student_ids and not targets.grades:
        return []
    conditions = []
    if targets.career_ids:
        conditions.append(Student.career_id.in_(targets.career_ids))
    if targets.grades and plan.school_year_id is not None:
        members = (
            select(ClassGroupMember.student_id)
            .join(ClassGroup, ClassGroup.class_group_id == ClassGroupMember.class_group_id)
            .where(
                ClassGroupMember.school_year_id == plan.school_year_id,
                ClassGroupMember.status == "enrolled",
                or_(
                    *(
                        (ClassGroup.career_id == g.career_id)
                        & (ClassGroup.grade_number == g.grade_number)
                        for g in targets.grades
                    )
                ),
            )
        )
        conditions.append(Student.student_id.in_(members))
    if targets.student_ids:
        conditions.append(Student.student_id.in_(targets.student_ids))
    month_end = last_day(parse_cycle(cycle))
    return [
        student
        for student in query.filter(or_(*conditions)).order_by(Student.enrollment_number)
        if student.student_id not in excluded
        and (student.admission_date is None or student.admission_date <= month_end)
    ]


def charged_student_ids(db: Session, plan: BillingPlan, cycle: str) -> set[int]:
    rows = (
        db.query(StudentAccount.student_id)
        .join(Charge, Charge.student_account_id == StudentAccount.student_account_id)
        .filter(Charge.billing_plan_id == plan.billing_plan_id, Charge.billing_cycle == cycle)
    )
    return {row[0] for row in rows}


def accounts_with_payment_plan(db: Session, student_ids: list[int]) -> set[int]:
    if not student_ids:
        return set()
    accounts = db.query(StudentAccount).filter(StudentAccount.student_id.in_(student_ids))
    return {a.student_id for a in accounts if any(p.active for p in a.payment_plans)}


def preview(db: Session, plan: BillingPlan, cycle: str) -> BillingPreview:
    ensure_cycle(plan, cycle)
    students = eligible_students(db, plan, cycle)
    charged = charged_student_ids(db, plan, cycle)
    pending = [s for s in students if s.student_id not in charged]
    with_plan = accounts_with_payment_plan(db, [s.student_id for s in pending])
    return BillingPreview(
        cycle=cycle,
        cycle_label=cycle_label(cycle),
        due_date=due_date(plan, cycle),
        amount=plan.amount,
        charge_description=f"{plan.charge_description} · {cycle_label(cycle)}",
        to_charge=len(pending),
        already_charged=len([s for s in students if s.student_id in charged]),
        total=money(cents(plan.amount) * len(pending)),
        with_payment_plan=len(with_plan),
        students=[
            BillingPreviewStudent(
                student_id=s.student_id,
                enrollment_number=s.enrollment_number,
                student_name=s.full_name,
                has_payment_plan=s.student_id in with_plan,
            )
            for s in pending[:PREVIEW_LIMIT]
        ],
    )


def generate(
    db: Session,
    plan: BillingPlan,
    cycle: str,
    user: User,
    reason: str,
    idempotency_key: str | None = None,
) -> BillingRun:
    lock_finance(db)
    if idempotency_key:
        previous = db.query(BillingRun).filter_by(idempotency_key=idempotency_key).first()
        if previous is not None:
            if previous.billing_plan_id != plan.billing_plan_id or previous.cycle != cycle:
                raise HTTPException(409, "La clave de la operación ya se usó para otro cobro")
            return previous
    if not plan.active:
        raise HTTPException(409, "El plan está pausado. Reactívalo para generar cargos")
    ensure_cycle(plan, cycle)
    charged = charged_student_ids(db, plan, cycle)
    pending = [s for s in eligible_students(db, plan, cycle) if s.student_id not in charged]
    description = f"{plan.charge_description} · {cycle_label(cycle)}"
    due = due_date(plan, cycle)
    try:
        for student in pending:
            account = get_account(db, student.student_id, write=True)
            account.ledger_version += 1
            charge = Charge(
                student_account_id=account.student_account_id,
                description=description,
                amount=plan.amount,
                due_date=due,
                created_by=user.user_id if user else None,
                billing_plan_id=plan.billing_plan_id,
                billing_cycle=cycle,
            )
            db.add(charge)
            db.flush()
            event(
                db,
                user,
                student.student_id,
                "charge.created",
                {
                    "charge_id": charge.charge_id,
                    "description": description,
                    "amount_cents": cents(plan.amount),
                    "due_date": due,
                    "billing_plan_id": plan.billing_plan_id,
                    "billing_cycle": cycle,
                },
            )
        run = BillingRun(
            billing_plan_id=plan.billing_plan_id,
            cycle=cycle,
            charge_count=len(pending),
            total=money(cents(plan.amount) * len(pending)),
            reason=reason,
            idempotency_key=idempotency_key,
            created_by=user.user_id if user else None,
        )
        db.add(run)
        db.flush()
    except IntegrityError as error:
        # Another run charged the same accounts first: the unique constraint holds.
        db.rollback()
        raise HTTPException(
            409, "Otro proceso generó este ciclo al mismo tiempo. Revisa la vista previa"
        ) from error
    event(
        db,
        user,
        None,
        "billing.run",
        {
            "billing_plan_id": plan.billing_plan_id,
            "cycle": cycle,
            "charge_count": run.charge_count,
            "total_cents": cents(run.total),
            "reason": reason,
            "generated_on": business_date(),
        },
    )
    return run
