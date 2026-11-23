"""School finance automation (Fase 3, block E; decisions of 23/11/2026).

Everything here is driven by ``FinancePolicy`` and starts disabled:

- Scheduled billing: each plan's month is generated ``billing_lead_days``
  before its due date (once; generation is idempotent per cycle).
- Sibling discount: students sharing a guardian marked "responsable de pago"
  are a family. In each month, the child with the highest tuition pays it in
  full; the 2nd and 3rd+ get the configured percentages on the charges of
  plans marked ``sibling_discount``.
- Late fee: one per overdue charge after the grace days, never compounded.
- Automatic hold: after ``hold_after_days`` overdue with at least
  ``hold_min_amount``; lifted automatically only when the job set it.

Each automatic adjustment has a unique ``automation_key``, so running the job
twice, or after a missed day, posts nothing twice.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.models.community_model import StudentGuardian
from app.models.finance_model import (
    BillingPlan,
    BillingRun,
    Charge,
    FinancePolicy,
    FinancialAdjustment,
    StudentAccount,
)
from app.models.student_model import Student
from app.services.account_statement import account_statement
from app.services.audit_log import record
from app.services.business_time import business_date
from app.services.finance_workflow import cents, event, lock_finance, money, now

SYSTEM_REASON = "Generación programada"


def policy_of(db: Session, write: bool = False) -> FinancePolicy:
    policy = db.query(FinancePolicy).order_by(FinancePolicy.finance_policy_id).first()
    if policy is None:
        policy = FinancePolicy(
            late_fee_enabled=False,
            grace_days=5,
            late_fee_kind="percent",
            late_fee_value=Decimal("5"),
            hold_enabled=False,
            hold_after_days=30,
            hold_min_amount=Decimal("0"),
            sibling_discount_enabled=False,
            sibling_second_percent=Decimal("10"),
            sibling_third_percent=Decimal("15"),
            auto_billing_enabled=False,
            billing_lead_days=10,
        )
        if write:
            db.add(policy)
            db.flush()
    return policy


# --- Families ---------------------------------------------------------------


def families(db: Session, student_ids: set[int] | None = None) -> list[set[int]]:
    """Groups of active students sharing a guardian responsible for payment."""
    links = (
        db.query(StudentGuardian.guardian_id, StudentGuardian.student_id)
        .join(Student, Student.student_id == StudentGuardian.student_id)
        .filter(StudentGuardian.financial_responsible.is_(True), Student.active.is_(True))
        .all()
    )
    by_guardian: dict[int, set[int]] = defaultdict(set)
    for guardian_id, student_id in links:
        by_guardian[guardian_id].add(student_id)
    # Merge guardians that share children (union of overlapping sets).
    groups: list[set[int]] = []
    for members in by_guardian.values():
        merged = set(members)
        for group in [g for g in groups if g & merged]:
            merged |= group
            groups.remove(group)
        groups.append(merged)
    groups = [g for g in groups if len(g) > 1]
    if student_ids is not None:
        groups = [g for g in groups if g & student_ids]
    return groups


def family_of(db: Session, student_id: int) -> set[int]:
    for group in families(db, {student_id}):
        return group
    return {student_id}


# --- Sibling discount -------------------------------------------------------


def percent_of(amount: Decimal, percent: Decimal) -> Decimal:
    return (Decimal(amount) * Decimal(percent) / Decimal(100)).quantize(
        Decimal("0.01"), ROUND_HALF_UP
    )


def apply_sibling_discounts(db: Session, cycle: str, student_ids: set[int], actor=None) -> int:
    """Discounts for the families of ``student_ids`` in ``cycle`` (idempotent)."""
    policy = policy_of(db)
    if not policy.sibling_discount_enabled or not student_ids:
        return 0
    posted = 0
    for family in families(db, student_ids):
        charges = (
            db.query(Charge, StudentAccount.student_id)
            .join(StudentAccount, StudentAccount.student_account_id == Charge.student_account_id)
            .join(BillingPlan, BillingPlan.billing_plan_id == Charge.billing_plan_id)
            .filter(
                StudentAccount.student_id.in_(family),
                Charge.billing_cycle == cycle,
                Charge.status == "posted",
                BillingPlan.sibling_discount.is_(True),
            )
            .all()
        )
        by_student: dict[int, list[Charge]] = defaultdict(list)
        for charge, student_id in charges:
            by_student[student_id].append(charge)
        # The highest tuition pays in full; ties go to the lowest student id.
        ranked = sorted(
            by_student, key=lambda sid: (-max(cents(c.amount) for c in by_student[sid]), sid)
        )
        for position, student_id in enumerate(ranked[1:], start=2):
            percent = (
                policy.sibling_second_percent if position == 2 else policy.sibling_third_percent
            )
            if not percent:
                continue
            for charge in by_student[student_id]:
                key = f"sibling:{charge.charge_id}"
                if (
                    db.query(FinancialAdjustment.adjustment_id)
                    .filter_by(automation_key=key)
                    .first()
                ):
                    continue
                amount = percent_of(charge.amount, percent)
                if not amount:
                    continue
                adjustment = FinancialAdjustment(
                    student_account_id=charge.student_account_id,
                    kind="discount",
                    description=f"Descuento por hermanos ({position}.º hijo, {percent} %) · "
                    f"{charge.description}",
                    amount=amount,
                    due_date=charge.due_date,
                    created_by=actor.user_id if actor else None,
                    status="posted",
                    charge_id=charge.charge_id,
                    automation_key=key,
                )
                db.add(adjustment)
                account = db.get(StudentAccount, charge.student_account_id)
                account.ledger_version += 1
                db.flush()
                event(
                    db,
                    actor,
                    student_id,
                    "adjustment.sibling_discount",
                    {
                        "adjustment_id": adjustment.adjustment_id,
                        "charge_id": charge.charge_id,
                        "position": position,
                        "percent": str(percent),
                        "amount_cents": cents(amount),
                    },
                )
                posted += 1
    return posted


# --- Late fees and holds ----------------------------------------------------


@dataclass
class DailyResult:
    today: date
    simulated: bool = False
    billing_runs: list[dict] = field(default_factory=list)
    sibling_discounts: int = 0
    late_fees: list[dict] = field(default_factory=list)
    holds_set: list[str] = field(default_factory=list)
    holds_lifted: list[str] = field(default_factory=list)


def late_fee_amount(policy: FinancePolicy, charge_amount: Decimal) -> Decimal:
    if policy.late_fee_kind == "fixed":
        return money(cents(policy.late_fee_value))
    return percent_of(charge_amount, policy.late_fee_value)


def overdue_state(db: Session, account) -> tuple[Decimal, date | None, list]:
    """(overdue amount, oldest overdue due date, overdue charge rows)."""
    statement = account_statement(db, account)
    overdue = [item for item in statement.obligations if item.status == "overdue"]
    oldest = min((item.due_date for item in overdue), default=None)
    return statement.overdue_balance, oldest, overdue


def apply_late_fees(db: Session, today: date, result: DailyResult, actor=None) -> None:
    policy = policy_of(db)
    if not policy.late_fee_enabled:
        return
    limit = today - timedelta(days=policy.grace_days)
    accounts = (
        db.query(StudentAccount)
        .join(Student, Student.student_id == StudentAccount.student_id)
        .filter(Student.active.is_(True))
        .order_by(StudentAccount.student_account_id)
    )
    for account in accounts:
        _, _, overdue = overdue_state(db, account)
        for item in overdue:
            # Fees apply to charges, never to other fees or adjustments.
            if item.type != "charge" or item.due_date >= limit:
                continue
            key = f"late:{item.obligation_id}"
            if db.query(FinancialAdjustment.adjustment_id).filter_by(automation_key=key).first():
                continue
            charge = db.get(Charge, item.obligation_id)
            amount = late_fee_amount(policy, charge.amount)
            if not amount:
                continue
            adjustment = FinancialAdjustment(
                student_account_id=account.student_account_id,
                kind="late_fee",
                description=f"Recargo por mora · {charge.description}",
                amount=amount,
                due_date=today,
                created_by=actor.user_id if actor else None,
                status="posted",
                charge_id=charge.charge_id,
                automation_key=key,
            )
            db.add(adjustment)
            account.ledger_version += 1
            db.flush()
            event(
                db,
                actor,
                account.student_id,
                "adjustment.late_fee",
                {
                    "adjustment_id": adjustment.adjustment_id,
                    "charge_id": charge.charge_id,
                    "amount_cents": cents(amount),
                },
            )
            result.late_fees.append(
                {
                    "student": account.student.full_name,
                    "charge": charge.description,
                    "amount": str(amount),
                }
            )


def hold_due(policy: FinancePolicy, today: date, overdue: Decimal, oldest: date | None) -> bool:
    return (
        oldest is not None
        and overdue > 0
        and (today - oldest).days >= policy.hold_after_days
        and overdue >= Decimal(policy.hold_min_amount)
    )


def refresh_auto_hold(db: Session, account, actor=None, today: date | None = None) -> str | None:
    """Set or lift this student's automatic hold; manual holds are never touched."""
    policy = policy_of(db)
    student = account.student
    today = today or business_date()
    overdue, oldest, _ = overdue_state(db, account)
    due = policy.hold_enabled and hold_due(policy, today, overdue, oldest)
    if due and not student.financial_hold:
        student.financial_hold = True
        student.financial_hold_source = "auto"
        record(
            db,
            actor,
            "student.financial_hold.auto_set",
            f"student:{student.student_id}",
            f"Bloqueo financiero automático: {overdue} vencido desde {oldest}",
        )
        return "set"
    if student.financial_hold and student.financial_hold_source == "auto" and not due:
        student.financial_hold = False
        student.financial_hold_source = None
        record(
            db,
            actor,
            "student.financial_hold.auto_lifted",
            f"student:{student.student_id}",
            "Bloqueo financiero automático levantado: cuenta al día",
        )
        return "lifted"
    return None


def apply_holds(db: Session, today: date, result: DailyResult, actor=None) -> None:
    policy = policy_of(db)
    query = db.query(StudentAccount).join(Student).filter(Student.active.is_(True))
    if not policy.hold_enabled:
        # Still lift automatic holds if the policy was turned off.
        query = query.filter(Student.financial_hold_source == "auto")
    for account in query.order_by(StudentAccount.student_account_id):
        change = refresh_auto_hold(db, account, actor, today)
        if change == "set":
            result.holds_set.append(account.student.full_name)
        elif change == "lifted":
            result.holds_lifted.append(account.student.full_name)


# --- Scheduled billing and the daily job -------------------------------------


def run_scheduled_billing(db: Session, today: date, result: DailyResult) -> None:
    from app.services import billing_plans

    policy = policy_of(db)
    if not policy.auto_billing_enabled:
        return
    horizon = today + timedelta(days=policy.billing_lead_days)
    for plan in db.query(BillingPlan).filter_by(active=True).order_by(BillingPlan.billing_plan_id):
        done = set(billing_plans.generated_cycles(db, plan))
        for cycle in billing_plans.plan_cycles(plan):
            if cycle in done or billing_plans.due_date(plan, cycle) > horizon:
                continue
            run = billing_plans.generate(db, plan, cycle, None, SYSTEM_REASON)
            charged = {
                row[0]
                for row in db.query(StudentAccount.student_id)
                .join(Charge, Charge.student_account_id == StudentAccount.student_account_id)
                .filter(
                    Charge.billing_plan_id == plan.billing_plan_id, Charge.billing_cycle == cycle
                )
            }
            result.sibling_discounts += apply_sibling_discounts(db, cycle, charged)
            result.billing_runs.append(
                {
                    "plan": plan.name,
                    "cycle": cycle,
                    "charges": run.charge_count,
                    "total": str(run.total),
                }
            )


def run_daily(db: Session, today: date | None = None, actor=None) -> DailyResult:
    """Billing, then late fees, then holds. The caller commits (or rolls back to simulate)."""
    today = today or business_date()
    lock_finance(db)
    result = DailyResult(today=today)
    run_scheduled_billing(db, today, result)
    apply_late_fees(db, today, result, actor)
    apply_holds(db, today, result, actor)
    record(
        db,
        actor,
        "finance.daily_job",
        "finance-policy",
        f"{today}: {len(result.billing_runs)} cobros generados, "
        f"{result.sibling_discounts} descuentos, {len(result.late_fees)} recargos, "
        f"{len(result.holds_set)} bloqueos, {len(result.holds_lifted)} desbloqueos",
    )
    return result


def last_scheduled_runs(db: Session, limit: int = 10) -> list[BillingRun]:
    return (
        db.query(BillingRun)
        .filter(BillingRun.created_by.is_(None))
        .order_by(BillingRun.billing_run_id.desc())
        .limit(limit)
        .all()
    )


def stamp(policy: FinancePolicy, actor) -> None:
    policy.updated_by = actor.user_id if actor else None
    policy.updated_at = now()
