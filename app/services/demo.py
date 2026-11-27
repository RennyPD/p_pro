"""Public demo institution (Fase 5, step G2).

A shared institution with the code ``demo`` (reserved: nobody can register
it), filled with the sample school and university and restored every night.
Visitors enter with one click per role. It never sends emails, never charges
cards and never sells plans; it is isolated like any other institution.
"""

import logging

from fastapi import HTTPException
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.db.database import settings
from app.db.tenant import current_tenant, set_tenant, tenant_bypass
from app.models.billing_model import Plan, Subscription
from app.models.institution_model import Institution
from app.models.platform_model import PlatformAuditLog
from app.models.user_model import User

DEMO_CODE = "demo"
DEMO_NAME = "Instituto Técnico Horizonte (demo)"
# Role offered on the demo page -> account created by the sample data.
DEMO_ACCOUNTS = {
    "admin": "admin.horizonte",
    "teacher": "profesor.01",
    "student": "estudiante.001",
    "guardian": "tutor.01",
}
logger = logging.getLogger("nexo.demo")


def demo_institution(db: Session) -> Institution | None:
    return db.query(Institution).filter(Institution.slug == DEMO_CODE).first()


def is_demo(db: Session) -> bool:
    """Whether the session acts for the demo institution."""
    institution_id = current_tenant(db)
    if institution_id is None:
        return False
    cache = db.info.setdefault("nexo_demo", {})
    if institution_id not in cache:
        institution = db.get(Institution, institution_id)
        cache[institution_id] = bool(institution and institution.slug == DEMO_CODE)
    return cache[institution_id]


def refuse_in_demo(db: Session, what: str) -> None:
    if is_demo(db):
        raise HTTPException(403, f"{what} no está disponible en la demo")


def ensure_demo_institution(db: Session) -> Institution:
    institution = demo_institution(db)
    if institution is None:
        from app.services.platform import now

        institution = Institution(
            name=DEMO_NAME,
            slug=DEMO_CODE,
            status="active",
            created_at=now(),
            status_changed_at=now(),
        )
        db.add(institution)
        db.flush()
    institution.status = "active"
    if not db.query(Subscription).filter_by(institution_id=institution.institution_id).first():
        unlimited = db.query(Plan).filter_by(code="institucional").first()
        db.add(
            Subscription(
                institution_id=institution.institution_id,
                plan_id=unlimited.plan_id,
                status="active",
                interval="yearly",
                provider="manual",
            )
        )
    db.flush()
    return institution


def clear_demo(db: Session, institution_id: int) -> None:
    """Delete every row of the demo institution, and its uploaded files."""
    from app.services.institution_data import delete_institution_rows

    delete_institution_rows(db, institution_id)


def reset_demo(engine: Engine) -> dict[str, int]:
    """Restore the demo to its sample data (nightly job and script)."""
    from app.legal import INSTITUTION_DOCUMENTS
    from app.services.legal import accept, pending_for_institution
    from scripts.seed_institution import seed_institution

    with Session(bind=engine) as db:  # system session
        institution = ensure_demo_institution(db)
        institution_id = institution.institution_id
        clear_demo(db, institution_id)
        db.commit()
    with Session(bind=engine) as db:
        set_tenant(db, institution_id)
        summary = seed_institution(db, clear=False)
        if pending_for_institution(db, institution_id):
            accept(
                db,
                INSTITUTION_DOCUMENTS,
                institution_id=institution_id,
                user_id=None,
                accepted_by="demo",
            )
        db.add(
            PlatformAuditLog(
                platform_admin_id=None,
                action="demo.reset",
                resource=f"institution:{institution_id}",
                detail="Demo restaurada con los datos de ejemplo",
            )
        )
        db.commit()
    return summary


def demo_user(db: Session, role: str) -> User:
    if not settings.demo_enabled:
        raise HTTPException(404, "La demo no está disponible")
    username = DEMO_ACCOUNTS.get(role)
    institution = demo_institution(db)
    if username is None or institution is None:
        raise HTTPException(404, "La demo no está disponible")
    user = (
        db.query(User)
        .filter(User.institution_id == institution.institution_id, User.username == username)
        .execution_options(**tenant_bypass())
        .first()
    )
    if user is None or not user.active:
        raise HTTPException(503, "La demo se está restaurando. Intenta en unos minutos")
    set_tenant(db, institution.institution_id)
    return user
