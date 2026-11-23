"""Finance reports (Fase 3 E): aging, income, expected vs collected, own cash.

Aging needs the oldest-first allocation of credits, so each account's buckets
come from its statement; listings paginate the candidate accounts in the
database (those with something due before today) and compute only that page.
"""

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import exists, or_
from sqlalchemy.orm import Session

from app.models.career_model import Career
from app.models.class_group_model import ClassGroup, ClassGroupMember
from app.models.community_model import Guardian, StudentGuardian
from app.models.configuration_model import SchoolYear
from app.models.finance_model import (
    BillingPlan,
    Charge,
    FinancialAdjustment,
    Payment,
    StudentAccount,
)
from app.models.student_model import Student
from app.models.user_model import User
from app.services.account_statement import account_statement
from app.services.business_time import business_date
from app.services.finance_automation import families
from app.services.finance_workflow import CREDIT_KINDS, cents, money

BUCKETS = ("current", "d1_30", "d31_60", "d61_90", "d90_plus")
METHODS = {"cash": "Efectivo", "transfer": "Transferencia", "card": "Tarjeta", "legacy": "Otro"}


def bucket_of(due: date, today: date) -> str:
    days = (today - due).days
    if days <= 0:
        return "current"
    if days <= 30:
        return "d1_30"
    if days <= 60:
        return "d31_60"
    if days <= 90:
        return "d61_90"
    return "d90_plus"


def aging_of(db: Session, account, today: date) -> tuple[dict[str, int], date | None]:
    """Remaining cents per bucket and the oldest overdue due date."""
    buckets = dict.fromkeys(BUCKETS, 0)
    oldest = None
    for item in account_statement(db, account).obligations:
        remaining = cents(item.remaining)
        if not remaining:
            continue
        bucket = bucket_of(item.due_date, today)
        buckets[bucket] += remaining
        if bucket != "current" and (oldest is None or item.due_date < oldest):
            oldest = item.due_date
    return buckets, oldest


def as_money(buckets: dict[str, int]) -> dict[str, Decimal]:
    values = {key: money(buckets[key]) for key in BUCKETS}
    values["total"] = money(sum(buckets.values()))
    return values


def current_year_id(db: Session, today: date) -> int | None:
    year = (
        db.query(SchoolYear)
        .filter(SchoolYear.start_date <= today, SchoolYear.end_date >= today)
        .first()
    ) or db.query(SchoolYear).order_by(SchoolYear.start_date.desc()).first()
    return year.school_year_id if year else None


def group_labels(db: Session, student_ids: list[int], today: date) -> dict[int, str]:
    """Group of the current school year ("1.º A · Secundaria"), else the program."""
    labels = {}
    year_id = current_year_id(db, today)
    if year_id is not None and student_ids:
        rows = (
            db.query(ClassGroupMember.student_id, ClassGroup)
            .join(ClassGroup, ClassGroup.class_group_id == ClassGroupMember.class_group_id)
            .filter(
                ClassGroupMember.school_year_id == year_id,
                ClassGroupMember.student_id.in_(student_ids),
                ClassGroupMember.status == "enrolled",
            )
        )
        labels = {student_id: group.label for student_id, group in rows}
    missing = [sid for sid in student_ids if sid not in labels]
    if missing:
        rows = (
            db.query(Student.student_id, Career.name)
            .join(Career, Career.career_id == Student.career_id)
            .filter(Student.student_id.in_(missing))
        )
        labels.update({student_id: name for student_id, name in rows})
    return labels


def family_labels(db: Session) -> dict[int, str]:
    labels: dict[int, str] = {}
    for family in families(db):
        names = (
            db.query(Guardian.first_name, Guardian.last_name)
            .join(StudentGuardian, StudentGuardian.guardian_id == Guardian.guardian_id)
            .filter(
                StudentGuardian.student_id.in_(family),
                StudentGuardian.financial_responsible.is_(True),
            )
            .distinct()
            .all()
        )
        label = "Familia " + " / ".join(f"{first} {last}" for first, last in names)
        for student_id in family:
            labels[student_id] = label
    return labels


def overdue_candidates(db: Session, today: date):
    """Active accounts with a posted debt due before today (filtered in the database)."""
    charge_due = exists().where(
        Charge.student_account_id == StudentAccount.student_account_id,
        Charge.status == "posted",
        Charge.due_date < today,
    )
    adjustment_due = exists().where(
        FinancialAdjustment.student_account_id == StudentAccount.student_account_id,
        FinancialAdjustment.status == "posted",
        FinancialAdjustment.kind.not_in(CREDIT_KINDS),
        FinancialAdjustment.due_date < today,
    )
    return (
        db.query(StudentAccount)
        .join(Student, Student.student_id == StudentAccount.student_id)
        .filter(Student.active.is_(True), or_(charge_due, adjustment_due))
    )


def aging_summary(db: Session, today: date) -> dict:
    totals = dict.fromkeys(BUCKETS, 0)
    groups: dict[str, dict] = {}
    overdue_students = 0
    accounts = overdue_candidates(db, today).order_by(StudentAccount.student_account_id)
    rows = [(account, *aging_of(db, account, today)) for account in accounts]
    labels = group_labels(db, [account.student_id for account, _, _ in rows], today)
    for account, buckets, oldest in rows:
        if oldest is None:
            continue
        overdue_students += 1
        label = labels.get(account.student_id, "Sin grupo")
        group = groups.setdefault(label, {"buckets": dict.fromkeys(BUCKETS, 0), "students": 0})
        group["students"] += 1
        for key in BUCKETS:
            totals[key] += buckets[key]
            group["buckets"][key] += buckets[key]
    return {
        "as_of": today,
        "totals": as_money(totals),
        "students_overdue": overdue_students,
        "groups": sorted(
            (
                {"label": label, "students": data["students"], **as_money(data["buckets"])}
                for label, data in groups.items()
            ),
            key=lambda item: -item["total"],
        ),
    }


def aging_accounts(db: Session, today: date, accounts: list) -> list[dict]:
    labels = group_labels(db, [a.student_id for a in accounts], today)
    family = family_labels(db)
    result = []
    for account in accounts:
        buckets, oldest = aging_of(db, account, today)
        student = account.student
        result.append(
            {
                "student_id": student.student_id,
                "student_name": student.full_name,
                "enrollment_number": student.enrollment_number,
                "group": labels.get(student.student_id, ""),
                "family": family.get(student.student_id),
                "financial_hold": student.financial_hold,
                "oldest_due": oldest,
                **as_money(buckets),
            }
        )
    return result


# --- Income and expected ----------------------------------------------------


def day_bounds(start: date, end: date) -> tuple[datetime, datetime]:
    # Payments are stored in UTC; the business day is America/Santo_Domingo (UTC-4).
    return (
        datetime.combine(start, time()) + timedelta(hours=4),
        datetime.combine(end + timedelta(days=1), time()) + timedelta(hours=4),
    )


def income(db: Session, start: date, end: date, group_by: str) -> dict:
    low, high = day_bounds(start, end)
    rows = (
        db.query(Payment, User.username)
        .outerjoin(User, User.user_id == Payment.created_by)
        .filter(Payment.status == "posted", Payment.paid_at >= low, Payment.paid_at < high)
        .order_by(Payment.paid_at)
        .all()
    )
    grouped: dict[str, list] = defaultdict(lambda: [0, 0])
    labels: dict[str, str] = {}
    for payment, username in rows:
        if group_by == "method":
            key = payment.method
            labels[key] = METHODS.get(key, key)
        elif group_by == "cashier":
            key = username or "sistema"
            labels[key] = key
        else:
            key = business_date(payment.paid_at).isoformat()
            labels[key] = key
        grouped[key][0] += 1
        grouped[key][1] += cents(payment.amount)
    return {
        "start": start,
        "end": end,
        "group_by": group_by,
        "payments": len(rows),
        "total": money(sum(cents(p.amount) for p, _ in rows)),
        "rows": [
            {"key": key, "label": labels[key], "payments": count, "total": money(total)}
            for key, (count, total) in sorted(grouped.items())
        ],
    }


def expected_vs_collected(db: Session, year: int) -> list[dict]:
    start, end = date(year, 1, 1), date(year, 12, 31)
    months = {
        f"{year}-{m:02d}": {"expected": 0, "collected": 0, "concepts": {}} for m in range(1, 13)
    }
    charges = (
        db.query(Charge, BillingPlan.charge_description)
        .outerjoin(BillingPlan, BillingPlan.billing_plan_id == Charge.billing_plan_id)
        .filter(Charge.status == "posted", Charge.due_date >= start, Charge.due_date <= end)
    )
    for charge, concept in charges:
        month = months[charge.due_date.strftime("%Y-%m")]
        month["expected"] += cents(charge.amount)
        name = concept or "Otros cargos"
        month["concepts"][name] = month["concepts"].get(name, 0) + cents(charge.amount)
    low, high = day_bounds(start, end)
    payments = db.query(Payment).filter(
        Payment.status == "posted", Payment.paid_at >= low, Payment.paid_at < high
    )
    for payment in payments:
        months[business_date(payment.paid_at).strftime("%Y-%m")]["collected"] += cents(
            payment.amount
        )
    return [
        {
            "month": key,
            "expected": money(value["expected"]),
            "collected": money(value["collected"]),
            "by_concept": {k: float(money(v)) for k, v in value["concepts"].items()},
        }
        for key, value in months.items()
    ]


def cashier_day(db: Session, user: User, day: date) -> dict:
    low, high = day_bounds(day, day)
    payments = (
        db.query(Payment)
        .filter(
            Payment.created_by == user.user_id,
            Payment.status == "posted",
            Payment.paid_at >= low,
            Payment.paid_at < high,
        )
        .all()
    )
    by_method: dict[str, int] = defaultdict(int)
    for payment in payments:
        by_method[METHODS.get(payment.method, payment.method)] += cents(payment.amount)
    return {
        "day": day,
        "payments": len(payments),
        "total": money(sum(cents(p.amount) for p in payments)),
        "by_method": {k: float(money(v)) for k, v in by_method.items()},
    }


def today() -> date:
    return business_date()
