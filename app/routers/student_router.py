from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.Sesssion import get_db

from app.schemas.student_schema import (
    StudentCreate,
    StudentUpdate,
    StudentOut
)

from app.services.student_service import (
    create_student_service,
    get_students_service,
    get_student_by_id_service,
    update_student_service,
    delete_student_service
)

router = APIRouter(
    prefix="/students",
    tags=["students"]
)

@router.post("/", response_model=StudentOut)
def create_student(
    student_data: StudentCreate,
    db: Session = Depends(get_db)
    ):
    return create_student_service(db, student_data)

@router.get("/", response_model=list[StudentOut])
def get_students(
    db: Session = Depends(get_db)
    ):

    return get_students_service(db)

@router.get("/{student_id}", response_model=StudentOut)
def get_student_by_id(
    student_id: int, 
    db: Session = Depends(get_db)):

    return get_student_by_id_service(db, student_id)


@router.put(
    "/{student_id}",
    response_model=StudentOut
)
def update_student(
    student_id: int,
    student_data: StudentUpdate,
    db: Session = Depends(get_db)
    ):
    return update_student_service(db, student_id, student_data)

@router.delete("/{student_id}")
def delete_student(
    student_id: int,
    db: Session = Depends(get_db)
    ):
    return delete_student_service(db, student_id)
