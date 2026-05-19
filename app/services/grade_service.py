from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.repositories.grade_repository import (
    create_grade,
    get_grades,
    get_grade_by_id,
    update_grade,
    delete_grade
)

from app.schemas.grade_schema import GradeCreate, GradeUpdate

def create_grade_service(db: Session, grade_data: GradeCreate):
    return create_grade(db, grade_data)

def get_grades_service(db: Session):
    return get_grades(db)

def get_grade_by_id_service(db: Session, grade_id: int):
    grade = get_grade_by_id(db, grade_id)

    if not grade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Grade not found"
        )

    return grade

def update_grade_service(db: Session, grade_id: int, grade_data: GradeUpdate):
    grade = update_grade(db, grade_id, grade_data)

    if not grade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Grade not found"
        )

    return grade

def delete_grade_service(db: Session, grade_id: int):
    grade = delete_grade(db, grade_id)

    if not grade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Grade not found"
        )

    return {"message": "Grade deleted successfully"}