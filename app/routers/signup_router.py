"""Public self sign-up of an institution (Fase 4, block D4).

The institution is created ``pending`` with everything it needs (block B)
and its administrator gets the welcome email: opening it verifies the address,
activates the institution and starts the free trial. Sign-ups never activated
free their code after 7 days. Abuse limits: 5 sign-ups per hour per address,
a hidden field that only bots fill in, reserved codes.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.db.database import settings
from app.db.Session import get_db
from app.models.billing_model import Plan
from app.models.institution_model import Institution
from app.services import platform as service
from app.services.email_service import deliver_after_commit
from app.services.rate_limit import PUBLIC, SIGNUP, per_address
from app.services.tenant_host import valid_code

router = APIRouter(prefix="/public/signup", tags=["sign-up"])
CLOSED = "El registro de instituciones no está disponible. Escribe al equipo de Nexo"
RECEIVED = (
    "Te enviamos un correo para activar la cuenta del administrador. Ábrelo en los próximos "
    "7 días para empezar la prueba gratuita"
)


class SignupPlan(BaseModel):
    code: str
    name: str
    description: str
    currency: str
    monthly_price: str
    max_students: int | None = None


class SignupConfig(BaseModel):
    enabled: bool
    trial_days: int
    plans: list[SignupPlan]


class Signup(BaseModel):
    name: str = Field(min_length=3, max_length=150)
    code: str = Field(min_length=3, max_length=40)
    institution_type: str = Field(pattern=r"^(university|school|both)$")
    admin_email: EmailStr
    plan_code: str = Field(default="profesional", min_length=2, max_length=40)
    enrollment_prefix: str = Field(
        default="EST", min_length=1, max_length=20, pattern=r"^[A-Za-z0-9-]+$"
    )
    # Hidden in the form: people leave it empty, simple bots fill it in.
    website: str = Field(default="", max_length=200)


def public_plans(db: Session) -> list[Plan]:
    return (
        db.query(Plan)
        .filter(Plan.public.is_(True), Plan.active.is_(True))
        .order_by(Plan.sort_order, Plan.plan_id)
        .all()
    )


@router.get("", response_model=SignupConfig, dependencies=[Depends(per_address(PUBLIC))])
def signup_config(db: Session = Depends(get_db)):
    return {
        "enabled": settings.signup_enabled,
        "trial_days": settings.billing_trial_days,
        "plans": [
            {
                "code": plan.code,
                "name": plan.name,
                "description": plan.description,
                "currency": plan.currency,
                "monthly_price": f"{plan.monthly_price:.2f}",
                "max_students": plan.max_students,
            }
            for plan in public_plans(db)
        ],
    }


@router.get("/code", dependencies=[Depends(per_address(PUBLIC))])
def code_available(code: str = Query(min_length=1, max_length=60), db: Session = Depends(get_db)):
    """Whether a code (and so the address <code>.<domain>) can be used."""
    code = code.strip().casefold()
    if not valid_code(code):
        return {"available": False, "reason": "Usa minúsculas, números y guiones (3 a 40)"}
    if db.query(Institution.institution_id).filter(Institution.slug == code).first():
        return {"available": False, "reason": "Ese código ya está en uso"}
    return {"available": True, "reason": None}


@router.post("", status_code=202, dependencies=[Depends(per_address(SIGNUP))])
def signup(data: Signup, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if not settings.signup_enabled:
        raise HTTPException(403, CLOSED)
    if data.website:
        return {"message": RECEIVED}  # a bot: same answer, nothing created
    if data.plan_code not in {plan.code for plan in public_plans(db)}:
        raise HTTPException(422, "Elige uno de los planes disponibles")
    service.lock_platform(db)
    service.create_institution(db, data, None, status="pending")
    db.commit()
    deliver_after_commit(background_tasks, db)
    return {"message": RECEIVED}
