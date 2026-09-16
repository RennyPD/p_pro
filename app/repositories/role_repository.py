from sqlalchemy.orm import Session

from app.models.role_model import Role
from app.schemas.role_schema import RoleCreate, RoleUpdate


def create_role(db: Session, role_data: RoleCreate) -> Role:

    new_role = Role(**role_data.model_dump())

    db.add(new_role)
    db.commit()
    db.refresh(new_role)

    return new_role


def get_roles(db: Session) -> list[Role]:
    return db.query(Role).all()


def get_role_by_id(db: Session, role_id: int) -> Role:
    return db.query(Role).filter(Role.role_id == role_id).first()


def update_role(db: Session, role_id: int, role_data: RoleUpdate) -> Role:

    role = get_role_by_id(db, role_id)

    if not role:
        return None

    update_data = role_data.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(role, key, value)

    db.commit()
    db.refresh(role)

    return role


def delete_role(db: Session, role_id: int) -> bool:

    role = get_role_by_id(db, role_id)

    if not role:
        return False

    db.delete(role)
    db.commit()

    return True
