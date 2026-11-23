"""School finance (Fase 3, block E): policy, daily job, family account, reports."""

import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.auth import (
    FINANCE_SCOPE,
    ensure_student_access,
    require_any_permission,
    require_permissions,
)
from app.db.Session import get_db
from app.models.community_model import Guardian, StudentGuardian
from app.models.finance_model import StudentAccount
from app.models.student_model import Student
from app.pagination import page_query, search
from app.routers.document_router import pdf_response
from app.schemas.school_finance_schema import (
    AgingAccount,
    AgingSummary,
    AutomationRun,
    CashierDay,
    ExpectedMonth,
    FamilyAccount,
    FinancePolicyIn,
    FinancePolicyOut,
    IncomeReport,
)
from app.services import finance_automation as automation
from app.services import finance_reports as reports
from app.services.account_statement import account_statement
from app.services.audit_log import record
from app.services.csv_export import spreadsheet_safe_row
from app.services.finance_workflow import cents, get_account, lock_finance, money

router = APIRouter(prefix="/finance", tags=["school finance"])
finance_viewer = require_permissions("finance.view")
finance_supervisor = require_permissions("finance.supervise")
finance_collector = require_permissions("finance.collect")
report_viewer = require_any_permission("finance.view", "reports.view")

POLICY_FIELDS = tuple(name for name in FinancePolicyIn.model_fields if name != "reason")


def policy_out(policy) -> dict:
    return {name: getattr(policy, name) for name in POLICY_FIELDS}


def csv_response(filename: str, header: list[str], rows: list[list]) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    for row in rows:
        writer.writerow(spreadsheet_safe_row(row))
    return Response(
        "﻿" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --- Policy and the daily job ------------------------------------------------


@router.get("/policy", response_model=FinancePolicyOut, dependencies=[Depends(finance_viewer)])
def get_policy(db: Session = Depends(get_db)):
    return policy_out(automation.policy_of(db))


@router.put("/policy", response_model=FinancePolicyOut)
def update_policy(
    data: FinancePolicyIn, db: Session = Depends(get_db), user=Depends(finance_supervisor)
):
    lock_finance(db)
    policy = automation.policy_of(db, write=True)
    changes = []
    for name in POLICY_FIELDS:
        before, after = getattr(policy, name), getattr(data, name)
        if str(before) != str(after):
            changes.append(f"{name}: {before} → {after}")
            setattr(policy, name, after)
    if changes:
        automation.stamp(policy, user)
        record(
            db,
            user,
            "finance.policy_updated",
            "finance-policy",
            f"{data.reason}; " + "; ".join(changes),
        )
    db.commit()
    return policy_out(policy)


def run_out(result: automation.DailyResult, simulated: bool) -> dict:
    return {
        "today": result.today,
        "simulated": simulated,
        "billing_runs": result.billing_runs,
        "sibling_discounts": result.sibling_discounts,
        "late_fees": result.late_fees,
        "holds_set": result.holds_set,
        "holds_lifted": result.holds_lifted,
    }


@router.post("/automation/simulate", response_model=AutomationRun)
def simulate_daily_job(
    day: date | None = None, db: Session = Depends(get_db), user=Depends(finance_supervisor)
):
    """What the daily job would do today; everything is rolled back."""
    lock_finance(db)
    result = automation.run_daily(db, day, user)
    out = run_out(result, True)
    db.rollback()
    return out


@router.post("/automation/run", response_model=AutomationRun)
def run_daily_job(db: Session = Depends(get_db), user=Depends(finance_supervisor)):
    """Run the daily job now (the scheduled script does the same every morning)."""
    lock_finance(db)
    result = automation.run_daily(db, None, user)
    db.commit()
    return run_out(result, False)


# --- Family account ----------------------------------------------------------


def family_account(db: Session, student_id: int) -> dict:
    members = sorted(automation.family_of(db, student_id))
    statements = [account_statement(db, get_account(db, sid)) for sid in members]
    responsible = (
        db.query(Guardian.first_name, Guardian.last_name)
        .join(StudentGuardian, StudentGuardian.guardian_id == Guardian.guardian_id)
        .filter(
            StudentGuardian.student_id.in_(members),
            StudentGuardian.financial_responsible.is_(True),
        )
        .distinct()
        .all()
    )
    return {
        "responsible": [f"{first} {last}" for first, last in responsible],
        "members": [
            {
                "student_id": s.student_id,
                "student_name": s.student_name,
                "enrollment_number": s.enrollment_number,
                "balance": s.balance,
                "overdue_balance": s.overdue_balance,
            }
            for s in statements
        ],
        "balance": money(sum(cents(s.balance) for s in statements)),
        "overdue_balance": money(sum(cents(s.overdue_balance) for s in statements)),
        "statements": statements,
    }


@router.get("/students/{student_id}/family", response_model=FamilyAccount)
def student_family(student_id: int, db: Session = Depends(get_db), user=Depends(finance_viewer)):
    ensure_student_access(user, student_id, FINANCE_SCOPE)
    if db.get(Student, student_id) is None:
        raise HTTPException(404, "Estudiante no encontrado")
    return family_account(db, student_id)


@router.get("/students/{student_id}/family.pdf")
def student_family_pdf(
    student_id: int, db: Session = Depends(get_db), user=Depends(finance_viewer)
):
    ensure_student_access(user, student_id, FINANCE_SCOPE)
    if db.get(Student, student_id) is None:
        raise HTTPException(404, "Estudiante no encontrado")
    family = family_account(db, student_id)
    lines = [
        "Responsables: " + (", ".join(family["responsible"]) or "Sin responsable de pago"),
        f"Balance familiar: {family['balance']:.2f}",
        f"Vencido: {family['overdue_balance']:.2f}",
        "",
    ]
    for statement in family["statements"]:
        lines.append(f"{statement.student_name} ({statement.enrollment_number})")
        lines.append(
            f"  Balance: {statement.balance:.2f} · Vencido: {statement.overdue_balance:.2f}"
        )
        for item in statement.obligations:
            if cents(item.remaining):
                lines.append(
                    f"  {item.due_date:%Y-%m-%d} | {item.description} | pendiente {item.remaining:.2f}"
                )
        lines.append("")
    return pdf_response(f"estado-familiar-{student_id}.pdf", "ESTADO DE CUENTA FAMILIAR", lines)


# --- Cashier and reports -----------------------------------------------------


@router.get("/cashier/today", response_model=CashierDay)
def my_cash_today(db: Session = Depends(get_db), user=Depends(finance_collector)):
    return reports.cashier_day(db, user, reports.today())


@router.get("/reports/aging", response_model=AgingSummary, dependencies=[Depends(report_viewer)])
def aging_report(db: Session = Depends(get_db)):
    return reports.aging_summary(db, reports.today())


def aging_page(db, response, q, career_id, skip, limit):
    today = reports.today()
    query = search(
        reports.overdue_candidates(db, today),
        q,
        Student.first_name,
        Student.last_name,
        Student.enrollment_number,
    )
    if career_id is not None:
        query = query.filter(Student.career_id == career_id)
    query = query.order_by(Student.last_name, Student.first_name, StudentAccount.student_account_id)
    return reports.aging_accounts(db, today, page_query(query, response, skip, limit))


@router.get(
    "/reports/aging/accounts",
    response_model=list[AgingAccount],
    dependencies=[Depends(report_viewer)],
)
def aging_accounts_report(
    response: Response,
    q: str | None = None,
    career_id: int | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return aging_page(db, response, q, career_id, skip, limit)


@router.get("/reports/aging/accounts.csv", dependencies=[Depends(report_viewer)])
def aging_accounts_csv(
    q: str | None = None,
    career_id: int | None = None,
    db: Session = Depends(get_db),
):
    rows = aging_page(db, Response(), q, career_id, 0, 5000)
    header = [
        "Matrícula",
        "Estudiante",
        "Grupo",
        "Familia",
        "Por vencer",
        "1–30",
        "31–60",
        "61–90",
        "Más de 90",
        "Total",
    ]
    return csv_response(
        f"morosidad-{reports.today()}.csv",
        header,
        [
            [
                r["enrollment_number"],
                r["student_name"],
                r["group"],
                r["family"] or "",
                r["current"],
                r["d1_30"],
                r["d31_60"],
                r["d61_90"],
                r["d90_plus"],
                r["total"],
            ]
            for r in rows
        ],
    )


def checked_income(db, start, end, group_by):
    if start > end:
        raise HTTPException(422, "El inicio debe ser anterior al fin")
    if (end - start).days > 366:
        raise HTTPException(422, "El reporte abarca como máximo un año")
    return reports.income(db, start, end, group_by)


@router.get("/reports/income", response_model=IncomeReport, dependencies=[Depends(report_viewer)])
def income_report(
    start: date,
    end: date,
    group_by: str = Query("day", pattern="^(day|method|cashier)$"),
    db: Session = Depends(get_db),
):
    return checked_income(db, start, end, group_by)


@router.get("/reports/income.csv", dependencies=[Depends(report_viewer)])
def income_csv(
    start: date,
    end: date,
    group_by: str = Query("day", pattern="^(day|method|cashier)$"),
    db: Session = Depends(get_db),
):
    report = checked_income(db, start, end, group_by)
    return csv_response(
        f"ingresos-{start}-{end}.csv",
        ["Grupo", "Pagos", "Total"],
        [[r["label"], r["payments"], r["total"]] for r in report["rows"]],
    )


@router.get(
    "/reports/expected",
    response_model=list[ExpectedMonth],
    dependencies=[Depends(report_viewer)],
)
def expected_report(year: int = Query(ge=2000, le=2100), db: Session = Depends(get_db)):
    return reports.expected_vs_collected(db, year)
