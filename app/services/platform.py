"""Platform super administration (Fase 4, block B; decisions of 24/11/2026).

- Separate accounts (``platform_admins``) with a mandatory second factor.
- Super administrators create, suspend and reactivate institutions and see
  usage counts; they never read an institution's records.
- Creating an institution prepares everything it needs to start and invites
  its first administrator by email (nobody else knows the password).
- Suspending blocks the institution's access with a message (read-only during
  a grace period arrives with plans, block D).
"""

import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.tenant import set_tenant, tenant_bypass
from app.models.billing_model import Plan, Subscription
from app.models.institution_model import Institution
from app.models.platform_model import PlatformAdmin, PlatformAuditLog
from app.models.role_model import Role
from app.models.security_model import AuditLog
from app.models.student_model import Student
from app.models.user_model import User
from app.security import hash_password, totp_step, verify_password
from app.services.tenant_host import valid_code
from app.services.write_locks import lock_scope

LOGIN_ERROR = "Correo, contraseña o código incorrectos"
SYSTEM_ROLES = (
    ("admin", "Administración", "Administración de la institución"),
    ("teacher", "Docencia", "Docentes"),
    ("student", "Estudiante", "Estudiantes"),
    ("guardian", "Tutoría", "Padres, madres y tutores"),
)


def now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def platform_record(
    db: Session, admin: PlatformAdmin | None, action: str, resource: str, detail: str = ""
) -> None:
    """Platform audit: who created, suspended or reactivated what, and when."""
    db.add(
        PlatformAuditLog(
            platform_admin_id=admin.platform_admin_id if admin else None,
            action=action,
            resource=resource,
            detail=detail,
            created_at=now(),
        )
    )


def lock_platform(db: Session) -> None:
    lock_scope(db, "platform")


# --- Accounts ----------------------------------------------------------------


def create_admin(db: Session, email: str, name: str, password: str, mfa_secret: str):
    email = email.strip().casefold()
    if db.query(PlatformAdmin).filter(PlatformAdmin.email == email).first():
        raise ValueError("Ya existe una cuenta de plataforma con ese correo")
    admin = PlatformAdmin(
        email=email,
        name=name.strip(),
        password=hash_password(password),
        mfa_secret=mfa_secret,
        active=True,
        session_version=0,
        created_at=now(),
    )
    db.add(admin)
    db.flush()
    platform_record(
        db, None, "platform_admin.created", f"platform-admin:{admin.platform_admin_id}", email
    )
    return admin


def authenticate(db: Session, email: str, password: str, code: str) -> PlatformAdmin:
    admin = db.query(PlatformAdmin).filter(PlatformAdmin.email == email.strip().casefold()).first()
    valid = admin is not None and admin.active and verify_password(password, admin.password)
    step = totp_step(admin.mfa_secret, code) if valid else None
    if (
        not valid
        or step is None
        or (admin.mfa_last_step is not None and step <= admin.mfa_last_step)
    ):
        platform_record(db, admin if valid else None, "platform.login_failed", "platform", email)
        db.commit()
        raise HTTPException(401, LOGIN_ERROR)
    admin.mfa_last_step = step
    admin.last_login_at = now()
    platform_record(db, admin, "platform.login", f"platform-admin:{admin.platform_admin_id}")
    return admin


# --- Institutions ------------------------------------------------------------


def usage(db: Session, institution_id: int) -> dict:
    """Counts only: the platform never reads an institution's records."""
    bypass = tenant_bypass()

    def count(model, *conditions):
        return (
            db.query(func.count())
            .select_from(model)
            .filter(model.institution_id == institution_id, *conditions)
            .execution_options(**bypass)
            .scalar()
        )

    last = (
        db.query(func.max(AuditLog.created_at))
        .filter(AuditLog.institution_id == institution_id)
        .execution_options(**bypass)
        .scalar()
    )
    from app.services.billing.limits import usage as plan_usage

    counts = plan_usage(db, institution_id)
    return {
        "students": count(Student, Student.active.is_(True)),
        "users": count(User),
        "staff": counts.staff,
        "storage_bytes": counts.storage_bytes,
        "last_activity": last,
    }


# --- Plans and subscriptions (Fase 4 D1) -----------------------------------------


def plan_by_code(db: Session, code: str) -> Plan:
    plan = db.query(Plan).filter(Plan.code == code.strip().casefold()).first()
    if plan is None:
        raise HTTPException(404, f"No existe el plan {code}")
    return plan


def plan_fields(plan: Plan) -> dict:
    return {column.name: getattr(plan, column.name) for column in Plan.__table__.columns}


def create_plan(db: Session, data, actor: PlatformAdmin) -> Plan:
    if db.query(Plan).filter(Plan.code == data.code).first():
        raise HTTPException(409, f"Ya existe un plan con el código {data.code}")
    plan = Plan(**data.model_dump(), created_at=now())
    db.add(plan)
    db.flush()
    platform_record(db, actor, "plan.created", f"plan:{plan.code}", plan_summary(plan))
    return plan


def update_plan(db: Session, plan: Plan, data, actor: PlatformAdmin) -> Plan:
    before = plan_summary(plan)
    for key, value in data.model_dump().items():
        setattr(plan, key, value)
    platform_record(
        db, actor, "plan.updated", f"plan:{plan.code}", f"{before} → {plan_summary(plan)}"
    )
    return plan


def plan_summary(plan: Plan) -> str:
    def limit(value, unit=""):
        return "sin límite" if value is None else f"{value}{unit}"

    return (
        f"{plan.name}: {plan.monthly_price}/{plan.yearly_price} {plan.currency}; "
        f"estudiantes {limit(plan.max_students)}, personal {limit(plan.max_staff)}, "
        f"archivos {limit(plan.storage_gb, ' GB')}"
    )


def start_trial(db: Session, institution_id: int, plan: Plan) -> Subscription:
    from app.db.database import settings

    subscription = Subscription(
        institution_id=institution_id,
        plan_id=plan.plan_id,
        status="trialing",
        interval="monthly",
        trial_ends_at=now() + timedelta(days=settings.billing_trial_days),
        provider="sandbox",
        updated_at=now(),
    )
    db.add(subscription)
    db.flush()
    return subscription


def change_subscription(db: Session, institution: Institution, data, actor) -> Subscription:
    """The platform assigns a plan (sales agreements, custom plans, trials)."""
    plan = plan_by_code(db, data.plan_code)
    subscription = (
        db.query(Subscription)
        .filter(Subscription.institution_id == institution.institution_id)
        .first()
    )
    if subscription is None:
        subscription = start_trial(db, institution.institution_id, plan)
    before = f"{subscription.plan.name if subscription.plan else '—'} ({subscription.status})"
    subscription.plan_id = plan.plan_id
    subscription.interval = data.interval
    if data.trial_days:
        subscription.status = "trialing"
        subscription.trial_ends_at = now() + timedelta(days=data.trial_days)
    elif subscription.status != "trialing":
        subscription.status = "active"
        subscription.past_due_since = subscription.read_only_since = None
    if subscription.status in ("active", "trialing"):
        from app.services.billing.lifecycle import lift_billing_suspension

        lift_billing_suspension(db, institution.institution_id)
    subscription.updated_at = now()
    db.flush()
    db.refresh(subscription)
    platform_record(
        db,
        actor,
        "subscription.changed",
        f"institution:{institution.institution_id}",
        f"{before} → {plan.name} ({subscription.status}); {data.reason.strip()}",
    )
    return subscription


def subscription_out(db: Session, institution_id: int) -> dict | None:
    subscription = (
        db.query(Subscription).filter(Subscription.institution_id == institution_id).first()
    )
    if subscription is None:
        return None
    return {
        "plan_code": subscription.plan.code,
        "plan_name": subscription.plan.name,
        "status": subscription.status,
        "interval": subscription.interval,
        "trial_ends_at": subscription.trial_ends_at,
        "current_period_end": subscription.current_period_end,
        "provider": subscription.provider,
    }


def institution_or_404(db: Session, institution_id: int) -> Institution:
    institution = db.get(Institution, institution_id)
    if institution is None:
        raise HTTPException(404, "Institución no encontrada")
    return institution


def create_institution(
    db: Session, data, actor: PlatformAdmin | None, status: str = "active"
) -> tuple[Institution, User]:
    """Create the institution, prepare it to start and invite its first administrator.

    ``actor`` is None for a self sign-up (block D4), which starts ``pending``
    until its administrator opens the invitation.
    """
    from app.models.configuration_model import InstitutionSettings
    from app.models.grading_scale_model import GradingScale
    from app.services.competencies import competency_groups
    from app.services.finance_automation import policy_of
    from app.services.permission_catalog import ensure_catalog
    from app.services.user_services import send_invitation

    code = data.code.strip().casefold()
    if not valid_code(code):
        raise HTTPException(
            422,
            "El código usa minúsculas, números y guiones (3 a 40 caracteres) y no puede ser "
            "una palabra reservada",
        )
    if db.query(Institution).filter(Institution.slug == code).first():
        raise HTTPException(409, f"Ya existe una institución con el código {code}")
    plan = plan_by_code(db, data.plan_code)
    institution = Institution(
        name=data.name.strip(),
        slug=code,
        status=status,
        contact_email=data.admin_email.strip().casefold(),
        created_at=now(),
        status_changed_at=now(),
    )
    db.add(institution)
    db.flush()
    start_trial(db, institution.institution_id, plan)
    school = data.institution_type in {"school", "both"}
    set_tenant(db, institution.institution_id)
    db.add(
        InstitutionSettings(
            institution_name=institution.name,
            enrollment_prefix=data.enrollment_prefix,
            enrollment_digits=4,
            next_enrollment_number=1,
            passing_grade=70,
            max_credits_per_period=24,
            institution_type=data.institution_type,
            students_view_finance=data.institution_type == "university",
            revision=0,
        )
    )
    roles = {}
    for name, label, description in SYSTEM_ROLES:
        role = Role(name=name, label=label, description=description)
        db.add(role)
        roles[name] = role
    db.flush()
    ensure_catalog(db)  # the built-in roles get their default permissions
    db.add(
        GradingScale(
            name="Numérica 0–100",
            kind="numeric",
            passing_value=70,
            decimals=0,
            is_default=True,
            completivo_average_weight=50,
            extraordinario_average_weight=30,
        )
    )
    policy_of(db, write=True)  # everything automatic starts disabled
    if school:
        competency_groups(db, create=True)
    admin = User(
        username=data.admin_email.strip().casefold(),
        email=data.admin_email.strip().casefold(),
        # Unusable until the invitation link sets a real password.
        password=hash_password(secrets.token_urlsafe(32)),
        role_id=roles["admin"].role_id,
    )
    db.add(admin)
    db.flush()
    send_invitation(db, admin)
    from app.services.audit_log import record

    record(
        db,
        None,
        "institution.created",
        f"institution:{institution.institution_id}",
        (f"Alta por la plataforma ({actor.email})" if actor else "Registro propio")
        + f"; primer administrador {admin.email}",
    )
    platform_record(
        db,
        actor,
        "institution.created",
        f"institution:{institution.institution_id}",
        f"{institution.name} ({code}); tipo {data.institution_type}; administrador {admin.email}; "
        f"prueba del plan {plan.name}",
    )
    return institution, admin


def change_status(db: Session, institution: Institution, status: str, reason: str, actor) -> None:
    if institution.status == status:
        raise HTTPException(
            409,
            "La institución ya está suspendida"
            if status == "suspended"
            else "La institución ya está activa",
        )
    before = institution.status
    institution.status = status
    institution.status_reason = reason.strip()
    institution.status_changed_at = now()
    platform_record(
        db,
        actor,
        "institution.suspended" if status == "suspended" else "institution.reactivated",
        f"institution:{institution.institution_id}",
        f"{institution.name}: {before} → {status}; {reason.strip()}",
    )


# --- Self sign-up (Fase 4, block D4) -----------------------------------------------

SIGNUP_EXPIRY_DAYS = 7


def activate_pending(db: Session, institution_id: int) -> None:
    """The administrator opened the invitation: the institution starts, and its trial too."""
    from app.db.database import settings

    institution = db.get(Institution, institution_id)
    if institution is None or institution.status != "pending":
        return
    institution.status = "active"
    institution.status_reason = "Correo del administrador verificado"
    institution.status_changed_at = now()
    subscription = (
        db.query(Subscription).filter(Subscription.institution_id == institution_id).first()
    )
    if subscription is not None and subscription.status == "trialing":
        subscription.trial_ends_at = now() + timedelta(days=settings.billing_trial_days)
    platform_record(
        db, None, "institution.activated", f"institution:{institution_id}", institution.name
    )


def expire_signups(db: Session, moment: datetime | None = None) -> list[str]:
    """Sign-ups never activated free their code after a week (data is kept)."""
    moment = moment or now()
    expired = []
    stale = db.query(Institution).filter(
        Institution.status == "pending",
        Institution.created_at <= moment - timedelta(days=SIGNUP_EXPIRY_DAYS),
    )
    for institution in stale:
        code = institution.slug
        institution.status = "abandoned"
        institution.slug = f"abandonada-{institution.institution_id}-{code}"[:60]
        institution.status_reason = "Registro sin activar en 7 días"
        institution.status_changed_at = moment
        platform_record(
            db,
            None,
            "institution.abandoned",
            f"institution:{institution.institution_id}",
            f"{institution.name}: el código {code} queda libre",
        )
        expired.append(code)
    return expired


# --- Final deletion (Fase 5, step G4) ------------------------------------------------

RETENTION_DAYS = 90
PURGEABLE = ("suspended", "abandoned")


def purge_available_on(institution: Institution) -> datetime | None:
    """First moment the institution's data may be deleted (90 days after it stopped)."""
    if institution.status not in PURGEABLE or institution.status_changed_at is None:
        return None
    return institution.status_changed_at + timedelta(days=RETENTION_DAYS)


def purge_institution(db: Session, institution: Institution, code: str, reason: str, actor) -> int:
    """Delete every record and file of a suspended or abandoned institution, for good."""
    from app.models.billing_model import BillingEvent
    from app.models.legal_model import LegalAcceptance
    from app.services.institution_data import delete_institution_rows

    if institution.institution_id == 1:
        raise HTTPException(409, "La institución principal de la instalación no se elimina")
    available = purge_available_on(institution)
    if available is None:
        raise HTTPException(409, "Solo se eliminan instituciones suspendidas o sin activar")
    if now() < available:
        raise HTTPException(
            409, f"Los datos se conservan 90 días: se podrán eliminar desde el {available:%d/%m/%Y}"
        )
    original = (
        institution.slug.split("-", 2)[-1]
        if institution.status == "abandoned"
        else institution.slug
    )
    if code.strip().casefold() not in {institution.slug, original}:
        raise HTTPException(422, "Escribe el código de la institución para confirmar")
    deleted = delete_institution_rows(db, institution.institution_id)
    for model in (Subscription, BillingEvent, LegalAcceptance):
        db.query(model).filter(model.institution_id == institution.institution_id).delete(
            synchronize_session=False
        )
    institution.status = "deleted"
    institution.status_reason = f"Datos eliminados: {reason.strip()}"[:250]
    institution.status_changed_at = now()
    institution.contact_email = None
    institution.slug = f"eliminada-{institution.institution_id}"
    platform_record(
        db,
        actor,
        "institution.purged",
        f"institution:{institution.institution_id}",
        f"{institution.name}: {deleted} registros eliminados; {reason.strip()}",
    )
    return deleted
