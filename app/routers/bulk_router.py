import csv
import io

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.auth import require_roles
from app.db.Session import get_db
from app.models.student_model import Student
from app.models.user_model import User
from app.schemas.student_schema import StudentCreate
from app.services.student_service import create_student_service

router = APIRouter(prefix="/bulk", tags=["bulk operations"])


@router.post("/students/import")
def import_students(
    content: bytes = Body(..., media_type="text/csv"),
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("admin")),
):
    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="The CSV must use UTF-8 encoding") from exc
    reader = csv.DictReader(io.StringIO(decoded))
    required = {"first_name", "last_name", "email", "telephone", "address", "career_id"}
    if not reader.fieldnames or not required.issubset(reader.fieldnames):
        raise HTTPException(
            status_code=422, detail=f"Required columns: {', '.join(sorted(required))}"
        )
    created = []
    errors = []
    for line, row in enumerate(reader, start=2):
        try:
            data = StudentCreate(
                first_name=row["first_name"],
                last_name=row["last_name"],
                email=row["email"],
                enrollment_number=row.get("enrollment_number") or None,
                telephone=row["telephone"],
                address=row["address"],
                career_id=int(row["career_id"]),
                active=(row.get("active", "true").casefold() not in {"false", "0", "no"}),
            )
            created.append(create_student_service(db, data).student_id)
        except (ValidationError, ValueError, HTTPException) as exc:
            db.rollback()
            errors.append({"line": line, "detail": str(exc)})
    return {"created": len(created), "student_ids": created, "errors": errors}


@router.get("/students/export")
def export_students(db: Session = Depends(get_db), _user: User = Depends(require_roles("admin"))):
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
    response = StreamingResponse(iter([output.getvalue()]), media_type="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = 'attachment; filename="estudiantes.csv"'
    return response
