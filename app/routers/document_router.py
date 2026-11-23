import re
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth import (
    FINANCE_SCOPE,
    ensure_own_finance_visible,
    ensure_section_access,
    ensure_student_document_access,
    get_current_user,
)
from app.db.Session import get_db
from app.models.section_model import Section
from app.models.student_model import Student
from app.models.user_model import User
from app.routers.finance_router import build_summary, get_or_create_account
from app.routers.record_router import RESULT_LABELS, STANDING_LABELS, build_transcript
from app.services.pdf_service import report_card_pdf, simple_pdf
from app.services.report_cards import build_report_card, has_school_card, member_for

router = APIRouter(prefix="/documents", tags=["documents"])


def pdf_response(filename: str, title: str, lines: list[str]) -> Response:
    return pdf_bytes_response(filename, simple_pdf(title, lines))


def pdf_bytes_response(filename: str, content: bytes) -> Response:
    fallback = re.sub(r"[^A-Za-z0-9_.-]", "_", filename)
    return Response(
        content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename, safe='')}",
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/students/{student_id}/transcript.pdf")
def transcript_pdf(
    student_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    ensure_student_document_access(db, user, student_id)
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")
    # School students get the school report card of their latest year (Fase 3 F).
    if has_school_card(db, student_id):
        card = build_report_card(db, member_for(db, student_id, None))
        return pdf_bytes_response(
            f"boletin-{card['enrollment_number']}-{card['school_year']}.pdf",
            report_card_pdf([card]),
        )
    record = build_transcript(db, student)
    lines = [
        f"Estudiante: {record.student_name}",
        f"Matricula: {record.enrollment_number}",
        f"Carrera: {record.career_name}",
        f"Promedio acumulado: {cumulative_text(record)}",
        f"Condicion academica: {STANDING_LABELS.get(record.academic_standing, record.academic_standing)}",
        f"Creditos aprobados con respaldo: {record.earned_credits}",
        f"Creditos por equivalencia (sin nota): {record.recognized_credits}",
        f"Inscripciones con creditos por verificar: {record.unverified_credit_courses}",
        "",
        *[
            f"{item.period} | {item.subject_code} | {item.credits if item.credits is not None else 'Por verificar'} créditos"
            f" | {item.average if item.average is not None else '-'} | "
            + (
                f"Equivalencia desde {item.origin_subject_code}; sin nota"
                if item.recognition_type == "equivalence"
                else RESULT_LABELS.get(item.result, item.result)
            )
            for item in record.courses
        ],
    ]
    return pdf_response(f"expediente-{record.enrollment_number}.pdf", "EXPEDIENTE ACADEMICO", lines)


@router.get("/students/{student_id}/statement.pdf")
def statement_pdf(
    student_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    ensure_student_document_access(db, user, student_id, FINANCE_SCOPE, area="finance")
    ensure_own_finance_visible(db, user, student_id)
    summary = build_summary(get_or_create_account(db, student_id))
    lines = [
        f"Estudiante: {summary.student_name}",
        f"Matricula: {summary.enrollment_number}",
        f"Cargos: {summary.total_charges:.2f}",
        f"Pagos: {summary.total_payments:.2f}",
        f"Ajustes: {summary.total_adjustments:.2f}",
        f"Balance: {summary.balance:.2f}",
        "",
        *[
            f"{item.date:%Y-%m-%d} | {item.type} | {item.description} | {item.amount:.2f}"
            for item in summary.transactions
        ],
    ]
    return pdf_response(f"estado-{summary.enrollment_number}.pdf", "ESTADO DE CUENTA", lines)


@router.get("/sections/{section_id}/roster.pdf")
def roster_pdf(
    section_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    section: Section = ensure_section_access(db, user, section_id)
    lines = [
        f"Seccion: {section.code}",
        f"Asignatura: {section.subject.code} - {section.subject.description}",
        "",
        *[
            f"{enrollment.student.enrollment_number} | {enrollment.student.first_name} {enrollment.student.last_name}"
            for enrollment in section.enrollments
        ],
    ]
    return pdf_response(f"lista-{section.code}.pdf", "LISTA DE ESTUDIANTES", lines)


@router.get("/students/{student_id}/enrollment-certificate.pdf")
def enrollment_certificate(
    student_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    ensure_student_document_access(db, user, student_id)
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")
    active = [item for item in student.enrollments if item.state in {"enrolled", "completed"}]
    lines = [
        f"Se certifica que {student.first_name} {student.last_name}",
        f"matricula {student.enrollment_number}, pertenece a {student.career.name}.",
        "",
        *[f"{item.period} | {item.section.subject.code} | {item.section.code}" for item in active],
    ]
    return pdf_response(
        f"constancia-{student.enrollment_number}.pdf", "CONSTANCIA DE INSCRIPCION", lines
    )


def cumulative_text(record) -> str:
    if record.cumulative_average is not None:
        return str(record.cumulative_average)
    if record.provisional_average is not None:
        return f"sin resultados definitivos (provisional {record.provisional_average})"
    return "sin resultados definitivos"


@router.get("/students/{student_id}/report-card.pdf")
def report_card(
    student_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    ensure_student_document_access(db, user, student_id)
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")
    # School students get the school report card of their latest year (Fase 3 F).
    if has_school_card(db, student_id):
        card = build_report_card(db, member_for(db, student_id, None))
        return pdf_bytes_response(
            f"boletin-{card['enrollment_number']}-{card['school_year']}.pdf",
            report_card_pdf([card]),
        )
    record = build_transcript(db, student)
    lines = [
        f"Estudiante: {record.student_name}",
        f"Matricula: {record.enrollment_number}",
        "",
        *[
            f"{item.subject_code} | {item.subject_name} | "
            + (
                f"Equivalencia desde {item.origin_subject_code}; sin nota"
                if item.recognition_type == "equivalence"
                else f"Nota: {item.average if item.average is not None else '-'}"
                f" ({RESULT_LABELS.get(item.result, item.result)})"
            )
            for item in record.courses
        ],
    ]
    return pdf_response(f"boletin-{record.enrollment_number}.pdf", "BOLETIN DE NOTAS", lines)
