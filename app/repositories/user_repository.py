import secrets

from sqlalchemy.orm import Session

from app.models.security_model import AuditLog, RefreshToken
from app.models.user_model import User
from app.schemas.user_schema import UserCreate, UserUpdate
from app.security import hash_password
from app.services.account_sessions import lock_account, revoke_account_sessions


def create_user(db: Session, user_data: UserCreate) -> User:

    data = user_data.model_dump(exclude={"invite"})
    # An invited account has no usable password until the person activates it.
    data["password"] = hash_password(data["password"] or secrets.token_urlsafe(32))
    new_user = User(**data)

    db.add(new_user)
    db.flush()

    return new_user


def get_users(db: Session) -> list[User]:
    return db.query(User).all()


def get_user_by_id(db: Session, user_id: int) -> User:
    return db.query(User).filter(User.user_id == user_id).first()


def update_user(db: Session, user_id: int, user_data: UserUpdate) -> User:

    user = get_user_by_id(db, user_id)

    if not user:
        return None

    update_data = user_data.model_dump(exclude_unset=True)
    if "password" in update_data:
        user = lock_account(db, user)
        update_data["password"] = hash_password(update_data["password"])
        revoke_account_sessions(db, user)

    for key, value in update_data.items():
        setattr(user, key, value)

    db.commit()
    db.refresh(user)

    return user


def delete_user(db: Session, user_id: int) -> bool:

    user = get_user_by_id(db, user_id)

    if not user:
        return False

    db.query(RefreshToken).filter(RefreshToken.user_id == user_id).delete()
    db.query(AuditLog).filter(AuditLog.user_id == user_id).update({"user_id": None})
    db.delete(user)
    db.commit()

    return True
