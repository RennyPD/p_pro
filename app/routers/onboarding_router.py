"""«Primeros pasos» for a new institution (Fase 4, block B).

Each step is done when its data exists; the interface links to the screens
that already exist. Read-only.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import require_permissions
from app.db.Session import get_db
from app.models.career_model import Career
from app.models.class_group_model import ClassGroup
from app.models.configuration_model import AcademicPeriod, SchoolYear
from app.models.curriculum_model import CurriculumCourse
from app.models.student_model import Student
from app.models.teacher_model import Teacher
from app.models.user_model import User
from app.services.institution_profile import institution_type, settings_of

router = APIRouter(tags=["onboarding"])


class OnboardingStep(BaseModel):
    key: str
    label: str
    description: str
    done: bool
    to: str


class OnboardingChecklist(BaseModel):
    steps: list[OnboardingStep]
    completed: int
    total: int


def exists(db: Session, model) -> bool:
    return db.query(model).first() is not None


@router.get("/onboarding/checklist", response_model=OnboardingChecklist)
def checklist(db: Session = Depends(get_db), _user=Depends(require_permissions("settings.manage"))):
    settings = settings_of(db)
    school = institution_type(db) in {"school", "both"}
    steps = [
        (
            "center",
            "Datos del centro",
            "Nombre, tipo, matrícula y datos del MINERD.",
            bool(settings and settings.revision > 0),
            "/settings/institution",
        ),
        (
            "year",
            "Año lectivo y períodos",
            "Crea el año y genera sus períodos.",
            exists(db, SchoolYear) and exists(db, AcademicPeriod),
            "/periods",
        ),
        (
            "programs",
            "Programas y grados" if school else "Programas",
            "Niveles o carreras que ofrece la institución.",
            exists(db, Career),
            "/careers",
        ),
        (
            "curriculum",
            "Plan de estudios",
            "Asignaturas de cada grado o período.",
            exists(db, CurriculumCourse),
            "/curriculum",
        ),
        ("teachers", "Docentes", "Registra al personal docente.", exists(db, Teacher), "/teachers"),
        (
            "students",
            "Estudiantes",
            "Registra o importa a los estudiantes.",
            exists(db, Student),
            "/students",
        ),
        (
            "users",
            "Usuarios",
            "Crea las cuentas e invita al equipo.",
            db.query(User).count() > 1,
            "/users",
        ),
    ]
    if school:
        steps.insert(
            4,
            (
                "groups",
                "Grupos",
                "Grupos fijos por grado (1.º A, 1.º B…).",
                exists(db, ClassGroup),
                "/class-groups",
            ),
        )
    items = [
        {"key": k, "label": label, "description": text, "done": done, "to": to}
        for k, label, text, done, to in steps
    ]
    return {
        "steps": items,
        "completed": sum(1 for item in items if item["done"]),
        "total": len(items),
    }
