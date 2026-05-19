from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends
from app.db.Session import get_db
from app.schemas.grade_schema import (
    GradeCreate,
    GradeUpdate,
    GradeOut
)
from app.services.grade_service import (
    create_grade_service,
    get_grades_service,
    get_grade_by_id_service,
    update_grade_service,
    delete_grade_service
)

router = APIRouter(
    prefix="/grades",
    tags=["grades"]
)

@router.post("/", response_model=GradeOut)
def create_grade(
    grade_data: GradeCreate,
    db: Session = Depends(get_db)
):
    return create_grade_service(db, grade_data)

@router.get("/", response_model=list[GradeOut])
def get_grades(
    db: Session = Depends(get_db)
):
    return get_grades_service(db)   

@router.get("/{grade_id}", response_model=GradeOut)
def get_grade_by_id(
    grade_id: int,
    db: Session = Depends(get_db)
):
    return get_grade_by_id_service(db, grade_id)

@router.put("/{grade_id}", response_model=GradeOut)
def update_grade(
    grade_id: int,
    grade_data: GradeUpdate,
    db: Session = Depends(get_db)
):
    return update_grade_service(db, grade_id, grade_data)

@router.delete("/{grade_id}")
def delete_grade(
    grade_id: int,
    db: Session = Depends(get_db)
):
    return delete_grade_service(db, grade_id)
