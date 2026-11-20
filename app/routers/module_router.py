from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_permissions
from app.db.Session import get_db
from app.models.career_model import Career
from app.models.configuration_model import AcademicPeriod
from app.models.section_model import Section
from app.models.student_model import Student
from app.models.subject_model import Subject
from app.models.teacher_model import Teacher
from app.models.user_model import User
from app.pagination import page_query
from app.services.governance_workflow import record
from app.services.write_locks import lock_access

router = APIRouter(prefix="/module-views", tags=["read-only modules"])
MODULES = {
    "students": (
        "Estudiantes",
        Student,
        "student_id",
        (
            ("Matrícula", "enrollment_number"),
            ("Nombre", "full_name"),
            ("Carrera", "career_name"),
        ),
    ),
    "teachers": (
        "Docentes",
        Teacher,
        "teacher_id",
        (
            ("Código", "employee_code"),
            ("Nombre", "full_name"),
            ("Especialidad", "specialty"),
        ),
    ),
    "careers": (
        "Carreras",
        Career,
        "career_id",
        (
            ("Código", "code"),
            ("Carrera", "name"),
            ("Título", "degree_title"),
        ),
    ),
    "subjects": (
        "Asignaturas",
        Subject,
        "subject_id",
        (
            ("Código", "code"),
            ("Asignatura", "description"),
        ),
    ),
    "sections": (
        "Secciones",
        Section,
        "section_id",
        (
            ("Código", "code"),
            ("Descripción", "description"),
            ("Período", "period_name"),
            ("Estado", "status"),
        ),
    ),
    "periods": (
        "Períodos",
        AcademicPeriod,
        "period_id",
        (
            ("Período", "name"),
            ("Año académico", "academic_year"),
            ("Estado", "status"),
        ),
    ),
}


class ModuleUpdate(BaseModel):
    modules: list[str] = Field(max_length=len(MODULES))


def module_list(keys):
    return [{"key": key, "label": spec[0]} for key, spec in MODULES.items() if key in keys]


@router.get("/mine")
def my_modules(user: User = Depends(get_current_user)):
    return module_list(user.module_views or [])


@router.get("/accounts/{user_id}")
def account_modules(
    user_id: int,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_permissions("users.manage", institutional=True)),
):
    account = db.get(User, user_id)
    if account is None:
        raise HTTPException(404, "La cuenta ya no está disponible")
    return {"available": module_list(MODULES), "selected": account.module_views or []}


@router.put("/accounts/{user_id}")
def update_modules(
    user_id: int,
    data: ModuleUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permissions("users.manage", institutional=True)),
):
    lock_access(db)
    account_modules(user_id, db, actor)
    selected = set(data.modules)
    if selected.difference(MODULES):
        raise HTTPException(422, "Selecciona únicamente módulos de la lista")
    account = db.get(User, user_id)
    old = sorted(account.module_views or [])
    account.module_views = sorted(selected)
    record(
        db, actor, "user.module_views.updated", f"user:{user_id}", f"{old} → {account.module_views}"
    )
    db.commit()
    return {"selected": sorted(selected)}


@router.get("/{module}")
def read_module(
    module: str,
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if module not in MODULES or module not in (user.module_views or []):
        raise HTTPException(403, "Tu cuenta no tiene acceso de consulta a este módulo")
    title, model, id_field, fields = MODULES[module]
    rows = page_query(db.query(model).order_by(getattr(model, id_field)), response, skip, limit)
    return {
        "title": title,
        "headings": [label for label, _ in fields],
        "rows": [[getattr(row, field) for _, field in fields] for row in rows],
    }
