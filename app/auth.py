from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, object_session

from app.db.Session import get_db
from app.db.tenant import set_tenant, tenant_bypass
from app.models.access_model import Permission, RolePermission
from app.models.community_model import StudentGuardian
from app.models.enrollment_model import Enrollment
from app.models.role_model import Role
from app.models.section_model import Section
from app.models.user_model import User
from app.observability import tag
from app.permissions import (
    INSTITUTIONAL_PERMISSIONS,
    LEGACY_BUNDLES,
    PERMISSION_SLUGS,
    SYSTEM_ROLE_DEFAULTS,
    default_scope,
    expand,
)
from app.security import decode_token_claims
from app.services.billing.access import enforce_plan

bearer_scheme = HTTPBearer(auto_error=False)


SUSPENDED_MESSAGE = (
    "La institución está suspendida. Contacta a su administración o al soporte de Nexo"
)
PENDING_MESSAGE = (
    "La institución aún no está activada. Abre el enlace del correo de bienvenida para empezar"
)
OTHER_INSTITUTION = "Esta sesión pertenece a otra institución. Inicia sesión en su dirección"


def ensure_institution_open(db: Session, institution_id: int) -> None:
    from app.models.institution_model import Institution

    institution = db.get(Institution, institution_id)
    if institution is not None and institution.status == "pending":
        raise HTTPException(status_code=403, detail=PENDING_MESSAGE)
    if institution is None or institution.status != "active":
        raise HTTPException(status_code=403, detail=SUSPENDED_MESSAGE)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Debes iniciar sesión",
            headers={"WWW-Authenticate": "Bearer"},
        )
    claims = decode_token_claims(credentials.credentials)
    if claims.get("scp", "institution") != "institution":
        # A platform (super administrator) token never opens institution data.
        raise HTTPException(status_code=401, detail="La sesión no es válida para esta institución")
    user_id, version = int(claims["sub"]), int(claims.get("sv", 0))
    # The account is read before its institution is known, then every query of
    # the request is limited to that institution (Fase 4 A).
    user = db.get(User, user_id, execution_options=tenant_bypass())
    if user is None:
        raise HTTPException(status_code=401, detail="La cuenta ya no existe")
    if claims.get("tid", user.institution_id) != user.institution_id:
        raise HTTPException(status_code=401, detail=OTHER_INSTITUTION)
    # Fase 4 B: a token is only valid at its own institution's address.
    from app.services.tenant_host import institution_for_host

    addressed = institution_for_host(db, request)
    if addressed is not None and addressed.institution_id != user.institution_id:
        raise HTTPException(status_code=401, detail=OTHER_INSTITUTION)
    set_tenant(db, user.institution_id)
    tag("institution_id", user.institution_id)
    enforce_plan(db)
    ensure_institution_open(db, user.institution_id)
    if user.session_version != version:
        raise HTTPException(status_code=401, detail="La sesión se revocó. Inicia sesión de nuevo")
    ensure_account_active(user)
    return user


INACTIVE_ACCOUNT_MESSAGE = "Tu cuenta está desactivada. Contacta a la administración"


def account_is_active(user: User) -> bool:
    """An account works only while it and its linked person profile are active."""
    if not user.active:
        return False
    if user.student is not None and not user.student.active:
        return False
    if user.teacher is not None and not user.teacher.active:
        return False
    return True


def ensure_account_active(user: User, status_code: int = 401) -> None:
    if not account_is_active(user):
        raise HTTPException(status_code=status_code, detail=INACTIVE_ACCOUNT_MESSAGE)


def assigned_permission_slugs(db: Session, role_id: int) -> set[str]:
    """Permission rows saved for the role, exactly as stored."""
    return {
        row[0]
        for row in db.query(Permission.slug)
        .join(RolePermission, RolePermission.permission_id == Permission.permission_id)
        .filter(RolePermission.role_id == role_id)
        .all()
    }


def institution_configured(db: Session) -> bool:
    from app.services.permission_catalog import institution_configured as configured

    return configured(db)


def role_permission_slugs(db: Session, role_id: int) -> set[str]:
    """Effective granular permissions of a role.

    Legacy broad grants unfold into their bundles. A database whose permission
    catalog is still empty (fresh install before seeding) gives the built-in
    roles their default permissions, so the system is usable from the start.
    """
    assigned = assigned_permission_slugs(db, role_id)
    if not assigned and not institution_configured(db):
        role = db.get(Role, role_id)
        if role is not None:
            return set(SYSTEM_ROLE_DEFAULTS.get(role.name.casefold(), ("", frozenset()))[1])
    return set(expand(assigned))


def ensure_role_within_actor(db: Session, actor: User, role_id: int | None) -> None:
    """Block privilege escalation: nobody manages a role with grants they do not hold.

    Applies to assigning the role to an account and to managing accounts that
    already carry it (password reset, deactivation, deletion).
    """
    if role_id is None or role_id == actor.role_id:
        return
    role = db.get(Role, role_id)
    if role is None:
        return
    target_slugs = role_permission_slugs(db, role_id)
    missing = target_slugs - role_permission_slugs(db, actor.role_id)
    # Without configured grants the system administrator role is still the top
    # role, so only another holder of that role may manage it.
    unconfigured_admin = (
        not target_slugs
        and role.name.casefold() == "admin"
        and actor.role.name.casefold() != "admin"
    )
    # Nor can an account hand out a wider data scope than its own.
    wider_scope = role.scope == "institution" and role_scope(actor) != "institution"
    if missing or unconfigured_admin or wider_scope:
        raise HTTPException(
            status_code=403,
            detail="No puedes gestionar cuentas ni roles con permisos que tu cuenta no tiene",
        )


def role_scope(user: User) -> str:
    return getattr(user.role, "scope", None) or default_scope(user.role.name)


SCOPE_AUDIENCE = {
    "institution": "admin",
    "sections": "teacher",
    "own": "student",
    "linked": "guardian",
}


def calendar_audience(user: User) -> str:
    """Calendar audience a role belongs to, from its scope (not its name)."""
    return SCOPE_AUDIENCE.get(role_scope(user), "admin")


def require_roles(*allowed_roles: str):
    allowed = {role.casefold() for role in allowed_roles}

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role.name.casefold() not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para esta acción",
            )
        return current_user

    return dependency


def require_permissions(
    *required_permissions: str, fallback_roles: tuple[str, ...] = (), institutional: bool = False
):
    """Require every listed permission (granular slugs from app.permissions).

    `institutional` additionally requires the role's scope to be the whole
    institution. `fallback_roles` is ignored: built-in roles get their default
    permissions from app.permissions when the catalog is empty.
    """
    required = set(required_permissions)
    unknown = required - PERMISSION_SLUGS - set(LEGACY_BUNDLES)
    if unknown:
        raise ValueError(f"Unknown permission(s): {', '.join(sorted(unknown))}")

    def dependency(
        current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
    ) -> User:
        # Institutional administration is not a teaching capability, even when
        # an older role still carries the broad academic.manage grant.
        needs_institution = institutional or bool(expand(required) & INSTITUTIONAL_PERMISSIONS)
        if needs_institution and not institutional_profile(current_user):
            raise HTTPException(
                status_code=403,
                detail="La administración académica requiere un perfil de personal institucional",
            )
        assigned = role_permission_slugs(db, current_user.role_id)
        if expand(required).issubset(assigned) or required.issubset(assigned):
            return current_user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Te falta el permiso: {', '.join(sorted(required - assigned))}",
        )

    dependency.nexo_permissions = tuple(sorted(required))
    return dependency


def require_any_permission(*slugs: str):
    """Require at least one of the listed permissions."""
    unknown = set(slugs) - PERMISSION_SLUGS
    if unknown:
        raise ValueError(f"Unknown permission(s): {', '.join(sorted(unknown))}")

    def dependency(
        current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
    ) -> User:
        if role_permission_slugs(db, current_user.role_id) & set(slugs):
            return current_user
        raise HTTPException(status_code=403, detail="No tienes permiso para esta acción")

    dependency.nexo_permissions = tuple(sorted(slugs))
    return dependency


def require_personal(permission: str, *scopes: str):
    """A personal-portal permission used from a role with one of `scopes` (own / linked)."""
    base = require_permissions(permission)

    def dependency(current_user: User = Depends(base)) -> User:
        linked = {"own": current_user.student_id, "linked": current_user.guardian_id}
        if role_scope(current_user) not in scopes or not any(linked.get(scope) for scope in scopes):
            raise HTTPException(
                status_code=403, detail="Esta función es para el portal personal vinculado"
            )
        return current_user

    dependency.nexo_permissions = tuple(sorted([permission]))
    return dependency


# Grants that open institution-wide reads. Accounts without them only see what
# their link (own student record, assigned sections, guardian children) allows.
ACADEMIC_SCOPE = (
    "students.view",
    "sections.view",
    "grades.view",
    "attendance.view",
    "reports.view",
)
FINANCE_SCOPE = ("finance.view", "reports.view")
DIRECTORY_SCOPE = (*ACADEMIC_SCOPE, "finance.view")
_PERMISSION_CACHE = "_nexo_permission_slugs"


def is_admin(user: User) -> bool:
    """Name of the built-in system administrator role.

    Do not use it to decide data access (CLAUDE.md, rule 3): use has_scope or
    require_permissions. It only identifies the protected built-in role.
    """
    return user.role.name.casefold() == "admin"


def institutional_profile(user: User) -> bool:
    """True when the role's scope is the whole institution.

    Accounts linked to a student or guardian never reach institution-wide data,
    whatever their role says.
    """
    if user.student_id is not None or user.guardian_id is not None:
        return False
    return role_scope(user) == "institution"


def user_permission_slugs(user: User) -> frozenset[str]:
    cached = user.__dict__.get(_PERMISSION_CACHE)
    if cached is None:
        db = object_session(user)
        cached = frozenset(role_permission_slugs(db, user.role_id)) if db else frozenset()
        user.__dict__[_PERMISSION_CACHE] = cached
    return cached


def has_scope(user: User, *grants: str) -> bool:
    """True when the account holds institution-wide reach through one of `grants`."""
    if not institutional_profile(user):
        return False
    return bool(user_permission_slugs(user) & set(grants))


def has_permission(user: User, *slugs: str) -> bool:
    """True when the account holds every listed permission (scope aside)."""
    return set(slugs).issubset(user_permission_slugs(user))


# Areas a guardian link can restrict (audit A1) and the column that grants each.
GUARDIAN_AREAS = {
    "academic": "can_view_academic",
    "attendance": "can_view_attendance",
    "finance": "can_view_finance",
    "tasks": "can_view_tasks",
}


def guardian_student_ids(db: Session, user: User, area: str | None = None) -> list[int]:
    """Students linked to the guardian account; with ``area``, only links that allow it."""
    if user.guardian_id is None:
        return []
    query = db.query(StudentGuardian.student_id).filter(
        StudentGuardian.guardian_id == user.guardian_id
    )
    if area is not None:
        query = query.filter(getattr(StudentGuardian, GUARDIAN_AREAS[area]).is_(True))
    return [row[0] for row in query]


def guardian_link(db: Session, user: User, student_id: int) -> StudentGuardian | None:
    if user.guardian_id is None:
        return None
    return (
        db.query(StudentGuardian)
        .filter_by(guardian_id=user.guardian_id, student_id=student_id)
        .first()
    )


def guardian_permissions(link: StudentGuardian) -> dict[str, bool]:
    return {area: bool(getattr(link, column)) for area, column in GUARDIAN_AREAS.items()}


def ensure_guardian_view(db: Session, user: User, student_id: int, area: str) -> StudentGuardian:
    """The guardian is linked to the student and the link allows ``area``."""
    link = guardian_link(db, user, student_id)
    if link is None:
        raise HTTPException(403, "Este estudiante no está vinculado a tu cuenta")
    if not getattr(link, GUARDIAN_AREAS[area]):
        raise HTTPException(403, "La institución restringió esta información para tu cuenta")
    return link


def ensure_student_access(
    user: User, student_id: int, grants: tuple[str, ...] = ACADEMIC_SCOPE
) -> None:
    if user.student_id == student_id or has_scope(user, *grants):
        return
    raise HTTPException(status_code=403, detail="Solo puedes consultar tu propio expediente")


def ensure_own_finance_visible(db: Session, user: User, student_id: int) -> None:
    """A student reads their own account only if the institution allows it.

    Staff with finance scope and linked guardians are not affected (decision
    of 21/11/2026, configurable in institution settings).
    """
    if user.student_id != student_id or has_scope(user, *FINANCE_SCOPE):
        return
    from app.services.institution_profile import student_sees_own_finance

    if not student_sees_own_finance(db, student_id):
        raise HTTPException(
            403, "La institución no muestra las finanzas en el portal del estudiante"
        )


def ensure_student_document_access(
    db: Session,
    user: User,
    student_id: int,
    grants: tuple[str, ...] = ACADEMIC_SCOPE,
    area: str = "academic",
) -> None:
    """Own record, linked guardian allowed to see ``area``, or institutional scope."""
    if user.student_id == student_id or has_scope(user, *grants):
        return
    if student_id in guardian_student_ids(db, user, area):
        return
    raise HTTPException(status_code=403, detail="Este documento está fuera del ámbito de tu cuenta")


def ensure_student_academic_access(db: Session, user: User, student_id: int) -> None:
    if user.student_id == student_id or has_scope(user, *ACADEMIC_SCOPE):
        return
    if user.teacher_id is not None:
        match = (
            db.query(Enrollment)
            .join(Enrollment.section)
            .filter(
                Enrollment.student_id == student_id,
                Section.teacher_id == user.teacher_id,
            )
            .first()
        )
        if match:
            return
    raise HTTPException(status_code=403, detail="El estudiante está fuera de tu ámbito académico")


def ensure_teacher_access(user: User, teacher_id: int) -> None:
    if user.teacher_id == teacher_id or has_scope(user, *ACADEMIC_SCOPE):
        return
    raise HTTPException(status_code=403, detail="Solo puedes consultar tu propio perfil docente")


def ensure_section_access(
    db: Session, user: User, section_id: int, allow_student: bool = False
) -> Section:
    section = db.get(Section, section_id)
    if section is None:
        raise HTTPException(status_code=404, detail="Sección no encontrada")
    if user.teacher_id == section.teacher_id and user.teacher_id is not None:
        return section
    if has_scope(user, *ACADEMIC_SCOPE):
        return section
    if allow_student and user.student_id is not None:
        enrolled = (
            db.query(Enrollment)
            .filter(
                Enrollment.section_id == section_id,
                Enrollment.student_id == user.student_id,
            )
            .first()
        )
        if enrolled:
            return section
    raise HTTPException(status_code=403, detail="La sección está fuera de tu ámbito académico")


def ensure_enrollment_access(db: Session, user: User, enrollment_id: int) -> Enrollment:
    enrollment = db.get(Enrollment, enrollment_id)
    if enrollment is None:
        raise HTTPException(status_code=404, detail="Inscripción no encontrada")
    if (
        user.student_id == enrollment.student_id
        or (user.teacher_id is not None and user.teacher_id == enrollment.section.teacher_id)
        or has_scope(user, *ACADEMIC_SCOPE)
    ):
        return enrollment
    raise HTTPException(status_code=403, detail="La inscripción está fuera de tu ámbito académico")
