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
from app.services.audit_log import changes, record, snapshot


def create_teacher_service(db: Session, teacher_data: TeacherCreate, actor):

    teachers = get_teachers(db)

    for teacher in teachers:
        if teacher.email == teacher_data.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Ya existe ese correo electrónico"
            )

    teacher = create_teacher(db, teacher_data)
    record(
        db,
        actor,
        "teacher.created",
        f"teacher:{teacher.teacher_id}",
        f"{teacher.first_name} {teacher.last_name} <{teacher.email}>",
    )
    db.commit()
    db.refresh(teacher)
    return teacher


def get_teachers_service(db: Session):
    return get_teachers(db)


def get_teacher_by_id_service(db: Session, teacher_id: int):

    teacher = get_teacher_by_id(db, teacher_id)

    if not teacher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Docente no encontrado")

    return teacher


def update_teacher_service(db: Session, teacher_id: int, teacher_data: TeacherUpdate, actor):
    fields = sorted(teacher_data.model_fields_set)
    before = snapshot(get_teacher_by_id_service(db, teacher_id), fields)
    teacher = update_teacher(db, teacher_id, teacher_data)

    if not teacher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Docente no encontrado")

    record(
        db,
        actor,
        "teacher.updated",
        f"teacher:{teacher_id}",
        changes(before, snapshot(teacher, fields)),
    )
    db.commit()
    db.refresh(teacher)
    return teacher


def delete_teacher_service(db: Session, teacher_id: int, actor):

    teacher = delete_teacher(db, teacher_id)

    if not teacher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Docente no encontrado")

    record(db, actor, "teacher.deactivated", f"teacher:{teacher_id}", "Baja de docente")
    db.commit()
    return {"message": "Docente eliminado"}
