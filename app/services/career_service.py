from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.repositories.career_repository import (
    create_career,
    get_careers,
    get_career_by_id,
    update_career,
    delete_career
)

from app.schemas.career_schema import CareerCreate, CareerUpdate

def create_career_service(db: Session, career_data: CareerCreate):
    return create_career(db, career_data)

def get_careers_service(db: Session):
    return get_careers(db)

def get_career_by_id_service(db: Session, career_id: int):
    career = get_career_by_id(db, career_id)

    if not career:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="career not found"
        )

    return career

def update_career_service(db: Session, career_id: int, career_data: CareerUpdate):
    career = update_career(db, career_id, career_data)

    if not career:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="career not found"
        )

    return career

def delete_career_service(db: Session, career_id: int):
    career = delete_career(db, career_id)

    if not career:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="career not found"
        )

    return {"message": "career deleted successfully"}