"""University, school or both (Fase 3, block A2).

The institution type is a setting; whether a program is a school level is
decided by its academic_level (MINERD levels: inicial, primario, secundario).
Everything school-specific in Fase 3 hangs on these two helpers, so a
university never sees grades or fixed courses and a school never sees credits.
"""

from sqlalchemy.orm import Session

from app.models.career_model import Career
from app.models.configuration_model import InstitutionSettings
from app.models.student_model import Student

INSTITUTION_TYPES = ("university", "school", "both")
SCHOOL_LEVELS = frozenset({"initial", "primary", "secondary"})
UNIVERSITY_LEVELS = frozenset({"technical", "undergraduate", "graduate", "postgraduate"})


def settings_of(db: Session) -> InstitutionSettings | None:
    """The active institution's settings (queries are filtered by institution)."""
    return db.query(InstitutionSettings).order_by(InstitutionSettings.settings_id).first()


def institution_type(db: Session) -> str:
    settings = settings_of(db)
    return getattr(settings, "institution_type", None) or "university"


def is_school_level(level: str | None) -> bool:
    return level in SCHOOL_LEVELS


def allowed_levels(kind: str) -> frozenset[str]:
    if kind == "school":
        return SCHOOL_LEVELS
    if kind == "university":
        return UNIVERSITY_LEVELS
    return SCHOOL_LEVELS | UNIVERSITY_LEVELS


def student_sees_own_finance(db: Session, student_id: int) -> bool:
    """Institution setting first; in a mixed institution school students never do
    (their guardians do), following the decision of 21/11/2026."""
    settings = settings_of(db)
    if settings is not None and not settings.students_view_finance:
        return False
    if institution_type(db) == "both":
        level = (
            db.query(Career.academic_level)
            .join(Student, Student.career_id == Career.career_id)
            .filter(Student.student_id == student_id)
            .scalar()
        )
        if is_school_level(level):
            return False
    return True
