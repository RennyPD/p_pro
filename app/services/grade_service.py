"""Grade lookups. Grades are written only through academic_grading.write_grade,
which checks the grading window, takes the academic lock and keeps the history."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.grade_model import Grade


def get_grade_by_id_service(db: Session, grade_id: int) -> Grade:
    grade = db.get(Grade, grade_id)

    if not grade:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nota no encontrada")

    return grade
