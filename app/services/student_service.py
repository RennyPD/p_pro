from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.repositories.student_repository import (
    create_student,
    get_students,
    get_student_by_id,
    update_student,
    delete_student
)

from app.schemas.student_schema import StudentCreate, StudentUpdate

def create_student_service(
        db: Session,
        student_data: StudentCreate
):
    students = get_students(db)

    for student in students:
        if student.email == student_data.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists"
            )

    return create_student(db, student_data)


def get_students_service(db: Session):
    return get_students(db)


def get_student_by_id_service(db: Session, student_id: int):

    student = get_student_by_id(db, student_id)

    if not student: 
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    return student

def update_student_service(
        db: Session,
        student_id: int,
        student_data: StudentUpdate
    ):

    student = update_student(db, student_id, student_data)

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    return student

def delete_student_service(db: Session, student_id: int):

    student = delete_student(db, student_id)

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    return {
        "message": "Student deleted successfully"
    }

