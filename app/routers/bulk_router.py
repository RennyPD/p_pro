import csv
import io

from fastapi import APIRouter, Body, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_permissions
from app.db.Session import get_db
from app.models.career_model import Career
from app.models.student_model import Student
from app.models.user_model import User
from app.schemas.student_schema import StudentCreate
from app.services.csv_export import spreadsheet_safe_row
from app.services.governance_workflow import lock_governance, record
from app.services.student_service import create_student_service

router = APIRouter(prefix="/bulk", tags=["bulk operations"])
academic_manager = require_permissions("students.manage")
STUDENT_COLUMNS = ("first_name", "last_name", "email", "telephone", "address")


@router.get("/students/template", dependencies=[Depends(academic_manager)])
def student_template():
    return Response(
        ",".join((*STUDENT_COLUMNS, "career_code", "enrollment_number", "active")) + "\r\n",
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="plantilla-estudiantes.csv"'},
    )


def student_from_row(db, row):
    if None in row or any(not str(row.get(field) or "").strip() for field in STUDENT_COLUMNS):
        raise HTTPException(422, "Completa el nombre, apellido, correo, teléfono y dirección")
    code, identifier = (str(row.get(field) or "").strip() for field in ("career_code", "career_id"))
    career = db.query(Career).filter_by(code=code).one_or_none() if code else None
    if not code and identifier:
        career = db.get(Career, int(identifier))
    if career is None:
        raise HTTPException(422, "Indica un código de carrera existente en career_code")
    if identifier and career.career_id != int(identifier):
        raise HTTPException(
            422, "El código y el identificador de carrera deben apuntar al mismo programa"
        )
    active = str(row.get("active") or "true").strip().casefold()
    if active not in {"true", "1", "sí", "si", "false", "0", "no"}:
        raise HTTPException(422, "Usa true o false para indicar si la matrícula está activa")
    return StudentCreate(
        **{field: row[field].strip() for field in STUDENT_COLUMNS},
        enrollment_number=(row.get("enrollment_number") or "").strip() or None,
        career_id=career.career_id,
        active=active in {"true", "1", "sí", "si"},
    )


def match_student(db, data):
    existing = db.query(Student).filter_by(email=data.email).first()
    if existing is None:
        return None
    fields = [*STUDENT_COLUMNS, "career_id", "active"]
    if data.enrollment_number:
        fields.append("enrollment_number")
    if any(getattr(existing, field) != getattr(data, field) for field in fields):
        raise HTTPException(409, "Ya existe una ficha distinta con ese correo. Revisa los datos")
    return existing


@router.post("/students/import")
def import_students(
    content: bytes = Body(..., media_type="text/csv"),
    db: Session = Depends(get_db),
    user: User = Depends(academic_manager),
    dry_run: bool = False,
):
    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(422, "Guarda el archivo CSV con codificación UTF-8") from exc
    try:
        reader = csv.reader(io.StringIO(decoded, newline=""), strict=True)
        fields = next(reader, [])
        if (
            not set(STUDENT_COLUMNS).issubset(fields)
            or not {"career_code", "career_id"}.intersection(fields)
            or len(set(fields)) != len(fields)
        ):
            raise HTTPException(422, "Usa la plantilla y completa sus encabezados sin duplicarlos")
        input_rows = []
        while True:
            line = reader.line_num + 1
            values = next(reader, None)
            if values is None:
                break
            if values:
                row = dict(zip(fields, values)) if len(values) == len(fields) else {None: None}
                input_rows.append((line, row))
    except csv.Error as exc:
        raise HTTPException(
            422, "El CSV tiene comillas o separadores inválidos. Revisa el archivo"
        ) from exc

    lock_governance(db)
    created = []
    errors = []
    rows = []
    for line, row in input_rows:
        try:
            with db.begin_nested():
                data = student_from_row(db, row)
                existing = match_student(db, data)
                if existing:
                    result = {
                        "line": line,
                        "status": "unchanged",
                        "student_id": existing.student_id,
                    }
                else:
                    student_id = create_student_service(db, data, commit=False).student_id
                    if dry_run:
                        result = {"line": line, "status": "valid"}
                    else:
                        result = {"line": line, "status": "created", "student_id": student_id}
            rows.append(result)
            if result["status"] == "created":
                created.append(result["student_id"])
        except (ValidationError, ValueError, TypeError, HTTPException, IntegrityError) as exc:
            if isinstance(exc, HTTPException):
                detail = exc.detail
            elif isinstance(exc, IntegrityError):
                detail = "Revisa que el correo, la matrícula y el documento sean únicos"
            elif isinstance(exc, ValidationError):
                fields = ", ".join(str(item["loc"][0]) for item in exc.errors() if item["loc"])
                detail = f"Corrige los campos de la fila: {fields}"
            else:
                detail = "Completa la fila y verifica que el identificador de carrera sea numérico"
            errors.append({"line": line, "detail": detail})
            rows.append({"line": line, "status": "rejected", "detail": detail})
    if dry_run:
        db.rollback()
    else:
        record(
            db,
            user,
            "students.imported",
            "students:import",
            f"Creados: {len(created)}; rechazados: {len(errors)}; "
            f"sin cambios: {len(rows) - len(created) - len(errors)}",
        )
        db.commit()
    return {"created": len(created), "student_ids": created, "errors": errors, "rows": rows}


@router.get("/students/export")
def export_students(db: Session = Depends(get_db), _user: User = Depends(academic_manager)):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "student_id",
            "enrollment_number",
            "first_name",
            "last_name",
            "email",
            "telephone",
            "address",
            "career_id",
            "active",
        ]
    )
    for student in db.query(Student).order_by(Student.student_id).all():
        writer.writerow(
            spreadsheet_safe_row(
                [
                    student.student_id,
                    student.enrollment_number,
                    student.first_name,
                    student.last_name,
                    student.email,
                    student.telephone,
                    student.address,
                    student.career_id,
                    student.active,
                ]
            )
        )
    response = StreamingResponse(iter([output.getvalue()]), media_type="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = 'attachment; filename="estudiantes.csv"'
    return response
