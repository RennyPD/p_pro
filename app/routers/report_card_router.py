"""School report cards and period reports (Fase 3, block F)."""

import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.auth import ensure_student_document_access, get_current_user
from app.db.Session import get_db
from app.models.configuration_model import SchoolYear
from app.models.user_model import User
from app.routers.document_router import pdf_bytes_response
from app.schemas.report_card_schema import (
    CommentIn,
    PeriodReport,
    PromotionSummaryRow,
    ReportCard,
)
from app.services import class_groups as groups
from app.services import report_cards as cards
from app.services.csv_export import spreadsheet_safe_row
from app.services.governance_workflow import lock_governance
from app.services.pdf_service import report_card_pdf, simple_pdf
from app.services.rate_limit import EXPORTS, per_account

router = APIRouter(tags=["report cards"])


def pdf(filename: str, content: bytes) -> Response:
    return pdf_bytes_response(filename, content)


def ensure_card_access(db: Session, user: User, student_id: int, member) -> None:
    """Own card, linked guardian with academic access, academic staff or the group's teachers."""
    try:
        ensure_student_document_access(db, user, student_id)
    except HTTPException:
        if not cards.teaches_group(db, user, member.class_group):
            raise


def card_for(db: Session, user: User, student_id: int, school_year_id: int | None) -> dict:
    member = cards.member_for(db, student_id, school_year_id)
    ensure_card_access(db, user, student_id, member)
    return cards.build_report_card(db, member)


@router.get("/students/{student_id}/report-card", response_model=ReportCard)
def report_card(
    student_id: int,
    school_year_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return card_for(db, user, student_id, school_year_id)


@router.get("/students/{student_id}/report-card.pdf", dependencies=[Depends(per_account(EXPORTS))])
def report_card_file(
    student_id: int,
    school_year_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    card = card_for(db, user, student_id, school_year_id)
    return pdf(
        f"boletin-{card['enrollment_number']}-{card['school_year']}.pdf", report_card_pdf([card])
    )


@router.get(
    "/class-groups/{class_group_id}/report-cards.pdf", dependencies=[Depends(per_account(EXPORTS))]
)
def group_report_cards(
    class_group_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    group = groups.ensure_group_access(db, user, class_group_id)
    members = sorted(groups.active_members(group), key=lambda m: m.student.last_name)
    if not members:
        raise HTTPException(409, "El grupo no tiene estudiantes")
    content = report_card_pdf([cards.build_report_card(db, m) for m in members])
    name = f"boletines-{group.grade_number}{group.name}-{group.school_year.name}.pdf"
    return pdf(name, content)


@router.put(
    "/class-groups/{class_group_id}/members/{member_id}/comments/{period_id}",
    response_model=ReportCard,
)
def save_comment(
    class_group_id: int,
    member_id: int,
    period_id: int,
    data: CommentIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    lock_governance(db)
    group = groups.ensure_group_access(db, user, class_group_id)
    member = groups.member_or_404(group, member_id)
    cards.save_comment(db, user, group, member, period_id, data.comment)
    db.commit()
    return cards.build_report_card(db, member)


@router.get("/class-groups/{class_group_id}/period-report", response_model=PeriodReport)
def period_report(
    class_group_id: int,
    period_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    group = groups.ensure_group_access(db, user, class_group_id)
    return cards.period_report(db, group, period_id)


def report_rows(report: dict) -> tuple[list[str], list[list]]:
    header = ["Matrícula", "Estudiante", *[s["code"] for s in report["subjects"]], "Asistencia %"]
    rows = [
        [
            student["enrollment_number"],
            student["student_name"],
            *[g["label"] or "" for g in student["grades"]],
            student["attendance"] if student["attendance"] is not None else "",
        ]
        for student in report["students"]
    ]
    rows.append(
        [
            "",
            "Promedio",
            *[s["average"] if s["average"] is not None else "" for s in report["subjects"]],
            "",
        ]
    )
    rows.append(
        [
            "",
            "% aprobados",
            *[
                s["passed_percentage"] if s["passed_percentage"] is not None else ""
                for s in report["subjects"]
            ],
            "",
        ]
    )
    return header, rows


@router.get(
    "/class-groups/{class_group_id}/period-report.csv", dependencies=[Depends(per_account(EXPORTS))]
)
def period_report_csv(
    class_group_id: int,
    period_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    group = groups.ensure_group_access(db, user, class_group_id)
    report = cards.period_report(db, group, period_id)
    header, rows = report_rows(report)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    for row in rows:
        writer.writerow(spreadsheet_safe_row(row))
    return Response(
        "﻿" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="cuadro-periodo.csv"'},
    )


@router.get(
    "/class-groups/{class_group_id}/period-report.pdf", dependencies=[Depends(per_account(EXPORTS))]
)
def period_report_pdf(
    class_group_id: int,
    period_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    group = groups.ensure_group_access(db, user, class_group_id)
    report = cards.period_report(db, group, period_id)
    header, rows = report_rows(report)
    lines = [
        f"{report['group_label']} · {report['period']}",
        f"Nota mínima: {report['passing_grade']:g}",
        "",
        " | ".join(header),
        *[" | ".join(str(value) for value in row) for row in rows],
    ]
    below = [s for s in report["students"] if s["below_passing"]]
    if below:
        lines += ["", "Por debajo de la nota mínima:"]
        lines += [f"{s['student_name']}: {', '.join(s['below_passing'])}" for s in below]
    return pdf("cuadro-periodo.pdf", simple_pdf("CUADRO DE CALIFICACIONES", lines))


@router.get(
    "/school-years/{school_year_id}/promotion-summary", response_model=list[PromotionSummaryRow]
)
def promotion_summary(
    school_year_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if db.get(SchoolYear, school_year_id) is None:
        raise HTTPException(404, "Año lectivo no encontrado")
    return cards.promotion_summary(db, user, school_year_id)
