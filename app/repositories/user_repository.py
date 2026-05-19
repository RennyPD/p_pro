from sqlalchemy.orm import Session
from app.models.user_model import User
from app.schemas.user_schema import UserCreate, UserUpdate

def create_user(db: Session, user_data: UserCreate) -> User:

    new_user = User(**user_data.model_dump())

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user

def get_users(db: Session) -> list[User]:
    return db.query(User).all()

def get_user_by_id(db: Session, user_id: int) -> User:
    return db.query(User).filter(User.user_id == user_id).first()

def update_user(db: Session, user_id: int, user_data: UserUpdate) -> User:

    user = get_user_by_id(db, user_id)

    if not user:
        return None
    
    update_data = user_data.model_dump(
        exclude_unset=True
    )

    for key, value in update_data.items():
        setattr(user, key, value)

    db.commit()
    db.refresh(user)

    return user

def delete_user(db: Session, user_id: int) -> bool:

    user = get_user_by_id(db, user_id)

    if not user:
        return False

    db.delete(user)
    db.commit()

    return True    

