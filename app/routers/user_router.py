from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import require_permissions
from app.db.Session import get_db
from app.schemas.user_schema import UserCreate, UserOut, UserUpdate
from app.services.user_services import (
    create_user_service,
    delete_user_service,
    get_user_by_id_service,
    get_users_service,
    update_user_service,
)

router = APIRouter(prefix="/users", tags=["users"])
access_manager = require_permissions("access.manage", fallback_roles=("admin",))


@router.post("/", response_model=UserOut, dependencies=[Depends(access_manager)])
def create_user(user_data: UserCreate, db: Session = Depends(get_db)):
    return create_user_service(db, user_data)


@router.get("/", response_model=list[UserOut], dependencies=[Depends(access_manager)])
def get_users(db: Session = Depends(get_db)):
    return get_users_service(db)


@router.get("/{user_id}", response_model=UserOut, dependencies=[Depends(access_manager)])
def get_user_by_id(user_id: int, db: Session = Depends(get_db)):
    return get_user_by_id_service(db, user_id)


@router.patch("/{user_id}", response_model=UserOut, dependencies=[Depends(access_manager)])
def update_user(user_id: int, user_data: UserUpdate, db: Session = Depends(get_db)):
    return update_user_service(db, user_id, user_data)


@router.delete("/{user_id}", dependencies=[Depends(access_manager)])
def delete_user(user_id: int, db: Session = Depends(get_db)):
    return delete_user_service(db, user_id)
