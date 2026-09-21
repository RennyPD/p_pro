from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import ensure_teacher_access, get_current_user, is_admin, require_permissions
from app.db.Session import get_db
from app.models.teacher_model import Teacher
from app.models.user_model import User
from app.schemas.teacher_schema import TeacherCreate, TeacherOut, TeacherUpdate
from app.services.teacher_service import (
    create_teacher_service,
    delete_teacher_service,
    get_teacher_by_id_service,
    update_teacher_service,
)

router = APIRouter(prefix="/teachers", tags=["teachers"])
teacher_manager = require_permissions("academic.manage", fallback_roles=("admin",))


@router.post("/", response_model=TeacherOut, dependencies=[Depends(teacher_manager)])
def create_teacher(teacher_data: TeacherCreate, db: Session = Depends(get_db)):
    return create_teacher_service(db, teacher_data)


@router.get("/", response_model=list[TeacherOut], dependencies=[Depends(get_current_user)])
def get_teachers(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Teacher)
    if is_admin(user):
        return query.all()
    if user.teacher_id is not None:
        return query.filter(Teacher.teacher_id == user.teacher_id).all()
    return []


@router.get("/{teacher_id}", response_model=TeacherOut, dependencies=[Depends(get_current_user)])
def get_teacher_by_id(
    teacher_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):

    ensure_teacher_access(user, teacher_id)
    return get_teacher_by_id_service(db, teacher_id)


@router.patch("/{teacher_id}", response_model=TeacherOut, dependencies=[Depends(teacher_manager)])
def update_teacher(teacher_id: int, teacher_data: TeacherUpdate, db: Session = Depends(get_db)):
    return update_teacher_service(db, teacher_id, teacher_data)


@router.delete("/{teacher_id}", dependencies=[Depends(teacher_manager)])
def delete_teacher(teacher_id: int, db: Session = Depends(get_db)):
    return delete_teacher_service(db, teacher_id)
