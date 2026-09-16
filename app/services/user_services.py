from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.user_repository import (
    create_user,
    delete_user,
    get_user_by_id,
    get_users,
    update_user,
)
from app.schemas.user_schema import UserCreate, UserUpdate


def create_user_service(db: Session, user_data: UserCreate):
    users = get_users(db)

    for user in users:
        if user.username == user_data.username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists"
            )

    return create_user(db, user_data)


def get_users_service(db: Session):
    return get_users(db)


def get_user_by_id_service(db: Session, user_id: int):
    user = get_user_by_id(db, user_id)

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return user


def update_user_service(db: Session, user_id: int, user_data: UserUpdate):
    user = update_user(db, user_id, user_data)

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return user


def delete_user_service(db: Session, user_id: int):
    user = delete_user(db, user_id)

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return {"message": "User deleted successfully"}
