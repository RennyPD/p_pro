from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.teacher_repository import (
    create_teacher,
    delete_teacher,
    get_teacher_by_id,
    get_teachers,
    update_teacher,
)
from app.schemas.teacher_schema import TeacherCreate, TeacherUpdate


def create_teacher_service(db: Session, teacher_data: TeacherCreate):

    teachers = get_teachers(db)

    for teacher in teachers:
        if teacher.email == teacher_data.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Email already exists"
            )

    return create_teacher(db, teacher_data)


def get_teachers_service(db: Session):
    return get_teachers(db)


def get_teacher_by_id_service(db: Session, teacher_id: int):

    teacher = get_teacher_by_id(db, teacher_id)

    if not teacher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")

    return teacher


def update_teacher_service(db: Session, teacher_id: int, teacher_data: TeacherUpdate):

    teacher = update_teacher(db, teacher_id, teacher_data)

    if not teacher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")

    return teacher


def delete_teacher_service(db: Session, teacher_id: int):

    teacher = delete_teacher(db, teacher_id)

    if not teacher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")

    return {"message": "Teacher deleted succesfully"}
