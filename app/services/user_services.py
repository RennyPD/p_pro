from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.community_model import Guardian
from app.models.role_model import Role
from app.models.student_model import Student
from app.models.teacher_model import Teacher
from app.repositories.user_repository import (
    create_user,
    delete_user,
    get_user_by_id,
    get_users,
    update_user,
)
from app.schemas.user_schema import UserCreate, UserUpdate


def validate_profile(db: Session, state: dict):
    role = db.get(Role, state["role_id"])
    if role is None:
        raise HTTPException(422, "Selecciona un rol existente para esta cuenta")
    linked = [
        (kind, model, state[field])
        for kind, model, field in (
            ("student", Student, "student_id"),
            ("teacher", Teacher, "teacher_id"),
            ("guardian", Guardian, "guardian_id"),
        )
        if state[field] is not None
    ]
    if len(linked) > 1:
        raise HTTPException(422, "La cuenta admite un solo vínculo de persona")
    if linked:
        kind, model, person_id = linked[0]
        if role.name.casefold() != kind:
            raise HTTPException(422, "Selecciona una persona del mismo perfil que el rol")
        if db.get(model, person_id) is None:
            raise HTTPException(422, "Selecciona una persona existente para esta cuenta")


def create_user_service(db: Session, user_data: UserCreate):
    validate_profile(db, user_data.model_dump())
    users = get_users(db)

    for user in users:
        if user.username == user_data.username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Ya existe ese nombre de usuario"
            )

    return create_user(db, user_data)


def get_users_service(db: Session):
    return get_users(db)


def get_user_by_id_service(db: Session, user_id: int):
    user = get_user_by_id(db, user_id)

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    return user


def update_user_service(db: Session, user_id: int, user_data: UserUpdate):
    current = get_user_by_id_service(db, user_id)
    state = {
        field: getattr(current, field)
        for field in ("role_id", "student_id", "teacher_id", "guardian_id")
    }
    state.update(user_data.model_dump(exclude_unset=True))
    validate_profile(db, state)
    user = update_user(db, user_id, user_data)

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    return user


def delete_user_service(db: Session, user_id: int):
    user = delete_user(db, user_id)

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    return {"message": "Usuario eliminado"}
