from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, object_session

from app.db.Session import get_db
from app.models.access_model import Permission, RolePermission
from app.models.community_model import StudentGuardian
from app.models.enrollment_model import Enrollment
from app.models.role_model import Role
from app.models.section_model import Section
from app.models.user_model import User
from app.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Debes iniciar sesión",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id, version = decode_access_token(credentials.credentials)
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="La cuenta ya no existe")
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


def role_permission_slugs(db: Session, role_id: int) -> set[str]:
    return {
        row[0]
        for row in db.query(Permission.slug)
        .join(RolePermission, RolePermission.permission_id == Permission.permission_id)
        .filter(RolePermission.role_id == role_id)
        .all()
    }


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
    if missing or unconfigured_admin:
        raise HTTPException(
            status_code=403,
            detail="No puedes gestionar cuentas ni roles con permisos que tu cuenta no tiene",
        )


def require_roles(*allowed_roles: str):
    allowed = {role.casefold() for role in allowed_roles}

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role.name.casefold() not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return dependency


def require_permissions(
    *required_permissions: str, fallback_roles: tuple[str, ...] = (), institutional: bool = False
):
    """Require configured permissions while keeping unconfigured legacy roles operable."""
    required = set(required_permissions)
    fallback = {role.casefold() for role in fallback_roles}

    def dependency(
        current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
    ) -> User:
        # Institutional administration is not a teaching capability, even when
        # an older role still carries the broad academic.manage grant.
        if (institutional or "academic.manage" in required) and not institutional_profile(
            current_user
        ):
            raise HTTPException(
                status_code=403,
                detail="Academic administration requires an institutional staff profile",
            )
        assigned = role_permission_slugs(db, current_user.role_id)
        if required.issubset(assigned):
            return current_user
        if (
            not assigned
            and db.query(Permission).count() == 0
            and current_user.role.name.casefold() in fallback
        ):
            return current_user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing permission: {', '.join(sorted(required - assigned))}",
        )

    return dependency


# Grants that open institution-wide reads. Accounts without them only see what
# their link (own student record, assigned sections, guardian children) allows.
ACADEMIC_SCOPE = ("academic.manage", "reports.view")
FINANCE_SCOPE = ("finance.manage", "reports.view")
DIRECTORY_SCOPE = ("academic.manage", "reports.view", "finance.manage")
_PERMISSION_CACHE = "_nexo_permission_slugs"


def is_admin(user: User) -> bool:
    """Name of the built-in system administrator role.

    Do not use it to decide data access (CLAUDE.md, rule 3): use has_scope or
    require_permissions. It only identifies the protected built-in role.
    """
    return user.role.name.casefold() == "admin"


def institutional_profile(user: User) -> bool:
    """Accounts tied to a teacher, student or guardian are scoped to that person."""
    if user.role.name.casefold() in {"teacher", "student", "guardian"}:
        return False
    if user.student_id is not None or user.guardian_id is not None:
        return False
    return user.teacher_id is None or is_admin(user)


def user_permission_slugs(user: User) -> frozenset[str]:
    cached = user.__dict__.get(_PERMISSION_CACHE)
    if cached is None:
        db = object_session(user)
        cached = frozenset(role_permission_slugs(db, user.role_id)) if db else frozenset()
        user.__dict__[_PERMISSION_CACHE] = cached
    return cached


def _legacy_admin(user: User) -> bool:
    # Same fallback as require_permissions: installations that never configured
    # permissions keep the built-in administrator operable.
    db = object_session(user)
    return (
        db is not None
        and is_admin(user)
        and not user_permission_slugs(user)
        and db.query(Permission.permission_id).first() is None
    )


def has_scope(user: User, *grants: str) -> bool:
    """True when the account holds institution-wide reach through one of `grants`."""
    if not institutional_profile(user):
        return False
    slugs = user_permission_slugs(user)
    if slugs & set(grants):
        return True
    return not slugs and _legacy_admin(user)


def guardian_student_ids(db: Session, user: User) -> list[int]:
    if user.guardian_id is None:
        return []
    return [
        row[0]
        for row in db.query(StudentGuardian.student_id).filter(
            StudentGuardian.guardian_id == user.guardian_id
        )
    ]


def ensure_student_access(
    user: User, student_id: int, grants: tuple[str, ...] = ACADEMIC_SCOPE
) -> None:
    if user.student_id == student_id or has_scope(user, *grants):
        return
    raise HTTPException(status_code=403, detail="Solo puedes consultar tu propio expediente")


def ensure_student_document_access(
    db: Session, user: User, student_id: int, grants: tuple[str, ...] = ACADEMIC_SCOPE
) -> None:
    """Own record, linked guardian, or institutional scope for the document's area."""
    if user.student_id == student_id or has_scope(user, *grants):
        return
    if student_id in guardian_student_ids(db, user):
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
