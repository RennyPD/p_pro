from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.Session import get_db
from app.services.career_service import (
    create_career_service,
    get_careers_service,
    get_career_by_id_service,
    update_career_service,
    delete_career_service
)
from app.schemas.career_schema import (
    CareerCreate,
    CareerUpdate,
    CareerOut
)

router = APIRouter(prefix="/careers",
                    tags=["career"])

@router.post("/", response_model=CareerOut)
def create_career(
    career_data: CareerCreate,
    db: Session = Depends(get_db)
):
    return create_career_service(db, career_data)

@router.get("/", response_model=list[CareerOut])
def get_careers(
    db: Session = Depends(get_db)
):
    return get_careers_service(db)

@router.get("/{career_id}", response_model=CareerOut)
def get_career_by_id(
    career_id: int,
    db: Session = Depends(get_db)
):
    return get_career_by_id_service(db, career_id)

@router.put("/{career_id}", response_model=CareerOut)
def update_career(
    career_id: int,
    career_data: CareerUpdate,
    db: Session = Depends(get_db)
):
    return update_career_service(db, career_id, career_data)

@router.delete("/{career_id}")
def delete_career(
    career_id: int,
    db: Session = Depends(get_db)
):
    return delete_career_service(db, career_id)
