from sqlalchemy.orm import Session
from app.models.career_model import Career
from app.schemas.career_schema import CareerCreate, CareerUpdate

def create_career(db: Session, career_data: CareerCreate) -> Career:

    new_career = Career(**career_data.model_dump())

    db.add(new_career)
    db.commit()
    db.refresh(new_career)

    return new_career

def get_careers(db: Session) -> list[Career]:
    return db.query(Career).all()

def get_career_by_id(db: Session, career_id: int) -> Career:
    return db.query(Career).filter(Career.career_id == career_id).first()

def update_career(db: Session, career_id: int, career_data: CareerUpdate) -> Career:

    career = get_career_by_id(db, career_id)

    if not career:
        return None
    
    update_data = career_data.model_dump(
        exclude_unset=True
    )

    for key, value in update_data.items():
        setattr(career, key, value)

    db.commit()
    db.refresh(career)

    return career

def delete_career(db: Session, career_id: int) -> bool:
    career = get_career_by_id(db, career_id)

    if not career:
        return False

    db.delete(career)
    db.commit()

    return True