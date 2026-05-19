from sqlalchemy.orm import Session
from app.models.grade_model import Grade
from app.schemas.grade_schema import GradeCreate, GradeUpdate

def create_grade(db: Session, grade_data: GradeCreate) -> Grade:

    new_grade = Grade(**grade_data.model_dump())

    db.add(new_grade)
    db.commit()
    db.refresh(new_grade)

    return new_grade

def get_grades(db: Session) -> list[Grade]:
    return db.query(Grade).all()

def get_grade_by_id(db: Session, grade_id: int) -> Grade:
    return db.query(Grade).filter(Grade.grade_id == grade_id).first()

def update_grade(db: Session, grade_id: int, grade_data: GradeUpdate) -> Grade:

    grade = get_grade_by_id(db, grade_id)

    if not grade:
        return None
    
    update_data = grade_data.model_dump(
        exclude_unset=True
    )

    for key, value in update_data.items():
        setattr(grade, key, value)

    db.commit()
    db.refresh(grade)

    return grade

def delete_grade(db: Session, grade_id: int) -> bool:
    grade = get_grade_by_id(db, grade_id)

    if not grade:
        return False

    db.delete(grade)
    db.commit()

    return True