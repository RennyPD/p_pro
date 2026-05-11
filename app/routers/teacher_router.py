from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.Sesssion import get_db

from app.schemas.teacher_schema import (
    TeacherCreate,
    TeacherUptade,
    TeacherOut
)

from app.services.teacher_service import(
    create_teacher_service,
    get_teachers_service,
    get_teacher_by_id_service,
    update_teacher_service,
    delete_teacher_service
)

router = APIRouter(
    prefix="/teachers",
    tags=["teachers"]
)

@router.post("/", response_model=TeacherOut)
def create_teacher(
    teacher_data: TeacherCreate,
    db: Session = Depends(get_db)
): 
    return create_teacher_service(db, teacher_data)

@router.get("/", response_model=list[TeacherOut])
def get_teachers(
    db: Session = Depends(get_db)
    ):

    return get_teachers_service(db)

@router.get("/{teacher_id}", response_model=TeacherOut)
def get_teacher_by_id(
    teacher_id: int, 
    db: Session = Depends(get_db)):

    return get_teacher_by_id_service(db, teacher_id)


@router.put(
    "/{teacher_id}",
    response_model=TeacherOut
)
def update_teacher(
    teacher_id: int,
    teacher_data: TeacherUptade,
    db: Session = Depends(get_db)
    ):
    return update_teacher_service(db, teacher_id, teacher_data)

@router.delete("/{teacher_id}")
def delete_teacher(
    teacher_id: int,
    db: Session = Depends(get_db)
    ):
    return delete_teacher_service(db, teacher_id)