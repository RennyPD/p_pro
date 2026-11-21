from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.auth import get_current_user, has_permission, require_any_permission
from app.db.Session import get_db
from app.models.career_model import Career
from app.models.configuration_model import AcademicPeriod
from app.models.subject_model import Subject
from app.models.user_model import User
from app.pagination import page_query

router = APIRouter(prefix="/module-views", tags=["read-only modules"])

# Read-only lists for roles that hold ``programs.view`` but not the permission of
# the full page (audit B4: one access system, the role's permissions). Students,
# teachers and sections are read on their own pages with their *.view permission.
MODULES = {
    "careers": (
        "Carreras",
        Career,
        "career_id",
        (
            ("Código", "code"),
            ("Carrera", "name"),
            ("Título", "degree_title"),
        ),
        "programs.manage",
    ),
    "subjects": (
        "Asignaturas",
        Subject,
        "subject_id",
        (
            ("Código", "code"),
            ("Asignatura", "description"),
        ),
        "programs.manage",
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
        "settings.manage",
    ),
}
VIEW_PERMISSION = "programs.view"


@router.get("/mine")
def my_modules(user: User = Depends(get_current_user)):
    """Modules shown under «Consulta»: readable and without their full page."""
    if not has_permission(user, VIEW_PERMISSION):
        return []
    return [
        {"key": key, "label": spec[0]}
        for key, spec in MODULES.items()
        if not has_permission(user, spec[4])
    ]


@router.get("/{module}")
def read_module(
    module: str,
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(require_any_permission(VIEW_PERMISSION, "programs.manage")),
):
    if module not in MODULES:
        raise HTTPException(404, "Ese módulo de consulta no existe")
    title, model, id_field, fields, _ = MODULES[module]
    rows = page_query(db.query(model).order_by(getattr(model, id_field)), response, skip, limit)
    return {
        "title": title,
        "headings": [label for label, _ in fields],
        "rows": [[getattr(row, field) for _, field in fields] for row in rows],
    }
