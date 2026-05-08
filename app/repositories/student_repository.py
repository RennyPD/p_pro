from sqlalchemy.orm import Session
from app.models.student_model import Student
from app.schemas.student_schema import StudentCreate, StudentUpdate

def create_student(
        db: Session,
        student_data: StudentCreate
):
    student = Student(
        **student_data.model_dump()
    )

    db.add(student)
    db.commit()
    db.refresh(student)

    return student

def get_students(db: Session):
    return db.query(Student).all()


def get_student_by_id(db: Session, student_id: int):
    return db.query(Student).filter(Student.student_id == student_id).first()


def update_student(
        db: Session,
        student_id: int,
        student_data: StudentUpdate
    ):

    student = get_student_by_id(db, student_id)

    if not student:
        return None
    
    update_data = student_data.model_dump(
        exclude_unset=True
        )
    
    for key, value in update_data.items():
        setattr(student, key, value)

        db.commit()
        db.refresh(student)

    return student


def delete_student(db: Session, student_id: int):
    
    student = get_student_by_id(
        db,
        student_id
    )

    if not student:
        return None
    
    student.active = False

    db.commit()

    return student