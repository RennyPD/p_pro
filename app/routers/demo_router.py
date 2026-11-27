"""One-click entry to the public demo (Fase 5, step G2)."""

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.database import settings
from app.db.Session import get_db
from app.routers.auth_router import issue_session
from app.schemas.auth_schema import TokenOut
from app.services.account_sessions import lock_account
from app.services.demo import DEMO_ACCOUNTS, demo_institution, demo_user
from app.services.rate_limit import PUBLIC, per_address

router = APIRouter(prefix="/public/demo", tags=["demo"])
ROLES = {
    "admin": "Administración",
    "teacher": "Docente",
    "student": "Estudiante",
    "guardian": "Familia",
}


class DemoLogin(BaseModel):
    role: str = Field(pattern=r"^(admin|teacher|student|guardian)$")


@router.get("", dependencies=[Depends(per_address(PUBLIC))])
def demo_info(db: Session = Depends(get_db)):
    available = settings.demo_enabled and demo_institution(db) is not None
    return {
        "enabled": available,
        "roles": [{"role": role, "label": ROLES[role]} for role in DEMO_ACCOUNTS]
        if available
        else [],
    }


@router.post("/login", response_model=TokenOut, dependencies=[Depends(per_address(PUBLIC))])
def demo_login(data: DemoLogin, response: Response, db: Session = Depends(get_db)):
    user = lock_account(db, demo_user(db, data.role))
    return issue_session(db, response, user)
