"""Statement of a student account: each installment and how much is paid.

Credits (payments, discounts, scholarships) cover obligations oldest first,
the same rule ``finance_workflow.summary`` uses for the overdue balance, so
both figures always agree.
"""

from app.models.finance_model import BillingPlan
from app.schemas.finance_schema import (
    AccountStatement,
    StatementConcept,
    StatementObligation,
    StatementPayment,
)
from app.services.business_time import business_date
from app.services.finance_workflow import (
    CREDIT_KINDS,
    active,
    cents,
    credits,
    money,
    obligations_of,
    plan_summary,
    summary,
    upcoming_due,
)


def obligation_rows(db, account):
    """(obligation tuple, model) pairs for every active charge and debit adjustment."""
    by_key = {("charge", c.charge_id): c for c in account.charges}
    by_key |= {("adjustment", a.adjustment_id): a for a in account.adjustments}
    return [(item, by_key[(item[2], item[3])]) for item in sorted(obligations_of(account))]


def concept_of(db, model, plans: dict) -> str:
    plan_id = getattr(model, "billing_plan_id", None)
    if plan_id is not None:
        if plan_id not in plans:
            plan = db.get(BillingPlan, plan_id)
            plans[plan_id] = plan.name if plan else model.description
        return plans[plan_id]
    if getattr(model, "kind", None) and model.kind not in CREDIT_KINDS:
        return "Recargos y ajustes"
    return model.description


def account_statement(db, account) -> AccountStatement:
    today = business_date()
    available = credits(account)
    plans: dict[int, str] = {}
    obligations = []
    concepts: dict[str, list[int]] = {}
    for (due, _, kind, identifier, amount), model in obligation_rows(db, account):
        paid = min(available, amount)
        available -= paid
        remaining = amount - paid
        concept = concept_of(db, model, plans)
        obligations.append(
            StatementObligation(
                type=kind,
                obligation_id=identifier,
                concept=concept,
                description=model.description,
                due_date=due,
                amount=money(amount),
                paid_amount=money(paid),
                remaining=money(remaining),
                status="paid"
                if not remaining
                else "overdue"
                if due < today
                else "partial"
                if paid
                else "pending",
            )
        )
        totals = concepts.setdefault(concept, [0, 0])
        totals[0] += amount
        totals[1] += paid
    totals = summary(account)
    due, due_amount = upcoming_due(account)
    return AccountStatement(
        student_id=account.student_id,
        student_name=account.student.full_name,
        enrollment_number=account.student.enrollment_number,
        balance=money(cents(totals.balance)),
        overdue_balance=money(cents(totals.overdue_balance)),
        next_due_date=due,
        next_due_amount=due_amount,
        obligations=obligations,
        concepts=[
            StatementConcept(
                concept=name,
                amount=money(amount),
                paid_amount=money(paid),
                remaining=money(amount - paid),
            )
            for name, (amount, paid) in sorted(concepts.items())
        ],
        payments=[
            StatementPayment(
                payment_id=p.payment_id,
                amount=p.amount,
                reference=p.reference,
                method=p.method,
                paid_at=p.paid_at,
                receipt_number=p.receipt_number,
            )
            for p in sorted(account.payments, key=lambda p: p.paid_at, reverse=True)
            if active(p)
        ],
        payment_plans=[
            plan_summary(account, plan)
            for plan in getattr(account, "payment_plans", []) or []
            if plan.active
        ],
    )
