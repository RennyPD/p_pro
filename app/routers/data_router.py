"""The institution's data: full export and a person's record (Fase 5, step G4)."""

from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.auth import ensure_student_access, require_permissions
from app.db.Session import get_db
from app.models.community_model import Guardian, StudentGuardian
from app.models.enrollment_model import Enrollment
from app.models.finance_model import StudentAccount
from app.models.fiscal_model import FiscalDocument
from app.models.grade_model import Grade
from app.models.operations_model import StudentDocument
from app.models.student_model import Student
from app.models.user_model import User
from app.services.audit_log import record
from app.services.institution_data import SECRET_COLUMNS, export_zip
from app.services.rate_limit import EXPORTS, per_account

router = APIRouter(prefix="/data", tags=["data rights"])
administrator = require_permissions("settings.manage", institutional=True)
registry = require_permissions("students.manage", institutional=True)


def plain(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    return value


def as_dict(row) -> dict:
    table = row.__table__
    hidden = SECRET_COLUMNS.get(table.name, set()) | {"institution_id"}
    return {c.name: plain(getattr(row, c.key)) for c in table.columns if c.name not in hidden}


@router.get("/export.zip", dependencies=[Depends(per_account(EXPORTS))])
def export_institution(db: Session = Depends(get_db), user: User = Depends(administrator)):
    """Everything the institution keeps in Nexo, to take it anywhere (also in read-only mode)."""
    content = export_zip(db, user.institution_id)
    record(db, user, "data.exported", "institution", f"Exportación completa ({len(content)} bytes)")
    db.commit()
    stamp = datetime.now(UTC).strftime("%Y%m%d")
    return Response(
        content,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="nexo-exportacion-{stamp}.zip"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/students/{student_id}/record.json", dependencies=[Depends(per_account(EXPORTS))])
def student_record(student_id: int, db: Session = Depends(get_db), user: User = Depends(registry)):
    """What the institution keeps about one student: to answer an access request (Ley 172-13)."""
    ensure_student_access(user, student_id, ("students.manage",))
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(404, "Estudiante no encontrado")
    links = db.query(StudentGuardian).filter_by(student_id=student_id).all()
    guardians = [db.get(Guardian, link.guardian_id) for link in links]
    account = db.query(StudentAccount).filter_by(student_id=student_id).first()
    enrollments = db.query(Enrollment).filter_by(student_id=student_id).all()
    enrollment_ids = [item.enrollment_id for item in enrollments] or [0]
    data = {
        "generado": datetime.now(UTC).isoformat(timespec="seconds"),
        "estudiante": as_dict(student),
        "cuentas_de_acceso": [as_dict(u) for u in db.query(User).filter_by(student_id=student_id)],
        "tutores": [
            as_dict(guardian) | {"vinculo": as_dict(link)}
            for guardian, link in zip(guardians, links, strict=True)
            if guardian is not None
        ],
        "inscripciones": [as_dict(item) for item in enrollments],
        "calificaciones": [
            as_dict(item)
            for item in db.query(Grade).filter(Grade.enrollment_id.in_(enrollment_ids))
        ],
        "documentos": [
            as_dict(item) for item in db.query(StudentDocument).filter_by(student_id=student_id)
        ],
        "finanzas": {
            "cuenta": as_dict(account) if account else None,
            "cargos": [as_dict(c) for c in account.charges] if account else [],
            "pagos": [as_dict(p) for p in account.payments] if account else [],
            "ajustes": [as_dict(a) for a in account.adjustments] if account else [],
            "comprobantes": [
                as_dict(d) for d in db.query(FiscalDocument).filter_by(student_id=student_id)
            ],
        },
    }
    if not account:
        data["finanzas"].pop("cuenta")
    record(
        db,
        user,
        "data.subject_export",
        f"student:{student_id}",
        "Expediente para solicitud de acceso",
    )
    db.commit()
    return data
