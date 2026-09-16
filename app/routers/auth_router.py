from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db.Session import get_db
from app.models.role_model import Role
from app.models.user_model import User
from app.repositories.user_repository import create_user
from app.schemas.auth_schema import BootstrapRequest, LoginRequest, TokenOut
from app.schemas.user_schema import UserCreate, UserOut
from app.security import create_access_token, verify_password

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/bootstrap", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def bootstrap_admin(data: BootstrapRequest, db: Session = Depends(get_db)):
    if db.query(User).first() is not None:
        raise HTTPException(status_code=409, detail="Bootstrap has already been completed")
    role = db.query(Role).filter(Role.name.ilike("admin")).first()
    if role is None:
        role = Role(name="admin", description="System administrator")
        db.add(role)
        db.flush()
    user_data = UserCreate(**data.model_dump(exclude={"role_id"}), role_id=role.role_id)
    user = create_user(db, user_data)
    return TokenOut(access_token=create_access_token(user.user_id), user=user)


@router.post("/login", response_model=TokenOut)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = (
        db.query(User)
        .filter(or_(User.username == data.username, User.email == data.username))
        .first()
    )
    if user is None or not verify_password(data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenOut(access_token=create_access_token(user.user_id), user=user)


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user
