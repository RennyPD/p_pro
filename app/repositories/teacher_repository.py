from sqlalchemy.orm import Session
from app.models.teacher_model import Teacher
from app.schemas.teacher_schema import TeacherCreate, TeacherUptade

def create_teacher(db: Session, teacher_data: TeacherCreate):

    teacher = Teacher(
        **teacher_data.model_dump()
    )

    db.add(teacher)
    db.commit()
    db.refresh(teacher)

    return teacher

def get_teachers(db: Session):
    return db.query(Teacher).all()

def get_teacher_by_id(db: Session, teacher_id: int):
    return db.query(Teacher).filter(Teacher.teacher_id == teacher_id).first()

def update_teacher(db: Session, teacher_id: int, teacher_data: TeacherUptade):

    teacher = get_teacher_by_id(db,teacher_id)

    if not teacher:
        return None
    
    update_data = teacher_data.model_dump(
        exclude_unset=True
    )

    for key, value in update_data.items():
        setattr(teacher, key, value)

    db.commit()
    db.refresh(teacher)

    return teacher

def delete_teacher(db:Session, teacher_id: int):

    teacher = get_teacher_by_id(db, teacher_id)

    if not teacher:
        return None

    teacher.active =False

    db.commit()

    return teacher    