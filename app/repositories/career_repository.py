from sqlalchemy.orm import Session

from app.models.career_model import Career
from app.schemas.career_schema import CareerCreate, CareerUpdate


def create_career(db: Session, data: CareerCreate) -> Career:
    career = Career(**data.model_dump(exclude_none=True))
    db.add(career)
    db.commit()
    db.refresh(career)
    return career


def get_careers(db: Session) -> list[Career]:
    return db.query(Career).all()


def get_career_by_id(db: Session, career_id: int) -> Career | None:
    return db.get(Career, career_id)


def update_career(db: Session, career_id: int, data: CareerUpdate) -> Career | None:
    career = get_career_by_id(db, career_id)
    if career is None:
        return None
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(career, key, value)
    db.commit()
    db.refresh(career)
    return career


def delete_career(db: Session, career_id: int) -> bool:
    career = get_career_by_id(db, career_id)
    if career is None:
        return False
    db.delete(career)
    db.commit()
    return True
