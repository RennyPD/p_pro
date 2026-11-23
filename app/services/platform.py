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
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.tenant import set_tenant, tenant_bypass
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
    return {
        "students": count(Student, Student.active.is_(True)),
        "users": count(User),
        "last_activity": last,
    }


def institution_or_404(db: Session, institution_id: int) -> Institution:
    institution = db.get(Institution, institution_id)
    if institution is None:
        raise HTTPException(404, "Institución no encontrada")
    return institution


def create_institution(db: Session, data, actor: PlatformAdmin) -> tuple[Institution, User]:
    """Create the institution, prepare it to start and invite its first administrator."""
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
    institution = Institution(
        name=data.name.strip(),
        slug=code,
        status="active",
        contact_email=data.admin_email.strip().casefold(),
        created_at=now(),
        status_changed_at=now(),
    )
    db.add(institution)
    db.flush()
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
        f"Alta por la plataforma ({actor.email}); primer administrador {admin.email}",
    )
    platform_record(
        db,
        actor,
        "institution.created",
        f"institution:{institution.institution_id}",
        f"{institution.name} ({code}); tipo {data.institution_type}; administrador {admin.email}",
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
