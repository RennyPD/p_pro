from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.repositories.career_repository import (
    create_career,
    delete_career,
    get_career_by_id,
    get_careers,
    update_career,
)
from app.schemas.career_schema import CareerCreate, CareerUpdate


def create_career_service(db: Session, data: CareerCreate):
    return create_career(db, data)


def get_careers_service(db: Session):
    return get_careers(db)


def get_career_service(db: Session, career_id: int):
    career = get_career_by_id(db, career_id)
    if career is None:
        raise HTTPException(status_code=404, detail="Career not found")
    return career


def update_career_service(db: Session, career_id: int, data: CareerUpdate):
    career = update_career(db, career_id, data)
    if career is None:
        raise HTTPException(status_code=404, detail="Career not found")
    return career


def delete_career_service(db: Session, career_id: int):
    if not delete_career(db, career_id):
        raise HTTPException(status_code=404, detail="Career not found")
    return {"message": "Career deleted successfully"}
