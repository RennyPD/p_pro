from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth import (
    ensure_section_access,
    ensure_student_academic_access,
    ensure_student_access,
    get_current_user,
)
from app.db.Session import get_db
from app.models.section_model import Section
from app.models.student_model import Student
from app.models.user_model import User
from app.routers.finance_router import build_summary, get_or_create_account
from app.routers.record_router import build_transcript
from app.services.pdf_service import simple_pdf

router = APIRouter(prefix="/documents", tags=["documents"])


def pdf_response(filename: str, title: str, lines: list[str]) -> Response:
    return Response(
        simple_pdf(title, lines),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/students/{student_id}/transcript.pdf")
def transcript_pdf(
    student_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    ensure_student_academic_access(db, user, student_id)
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")
    record = build_transcript(db, student)
    lines = [
        f"Estudiante: {record.student_name}",
        f"Matricula: {record.enrollment_number}",
        f"Carrera: {record.career_name}",
        f"Promedio acumulado: {record.cumulative_average}",
        f"Creditos aprobados: {record.earned_credits}",
        "",
        *[
            f"{item.period} | {item.subject_code} | {item.average or '-'} | {item.result}"
            for item in record.courses
        ],
    ]
    return pdf_response(f"expediente-{record.enrollment_number}.pdf", "EXPEDIENTE ACADEMICO", lines)


@router.get("/students/{student_id}/statement.pdf")
def statement_pdf(
    student_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    ensure_student_access(user, student_id)
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
