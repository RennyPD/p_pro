from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.Session import get_db
from app.models.access_model import Permission, RolePermission
from app.models.enrollment_model import Enrollment
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
            detail="Inicia sesión para continuar",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id, version = decode_access_token(credentials.credentials)
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="La cuenta ya no existe")
    if user.session_version != version:
        raise HTTPException(status_code=401, detail="La sesión se revocó. Inicia sesión de nuevo")
    return user


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
    """Require configured permissions while keeping unconfigured legacy roles operable."""
    required = set(required_permissions)
    fallback = {role.casefold() for role in fallback_roles}

    def dependency(
        current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
    ) -> User:
        # Institutional administration is not a teaching capability, even when
        # an older role still carries the broad academic.manage grant.
        if (institutional or "academic.manage" in required) and (
            current_user.role.name.casefold() in {"teacher", "student", "guardian"}
            or (
                not is_admin(current_user)
                and (current_user.teacher_id is not None or current_user.student_id is not None)
            )
        ):
            raise HTTPException(
                status_code=403,
                detail="La administración académica requiere un perfil del personal institucional",
            )
        assigned = {
            row[0]
            for row in db.query(Permission.slug)
            .join(RolePermission, RolePermission.permission_id == Permission.permission_id)
            .filter(RolePermission.role_id == current_user.role_id)
            .all()
        }
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
            detail=f"Te falta el permiso: {', '.join(sorted(required - assigned))}",
        )

    return dependency


def is_admin(user: User) -> bool:
    return user.role.name.casefold() == "admin"


def ensure_student_access(user: User, student_id: int) -> None:
    if not is_admin(user) and user.student_id != student_id:
        raise HTTPException(status_code=403, detail="Solo puedes consultar tu propio expediente")


def ensure_student_academic_access(db: Session, user: User, student_id: int) -> None:
    if is_admin(user) or user.student_id == student_id:
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
    raise HTTPException(status_code=403, detail="Este estudiante está fuera de tu ámbito académico")


def ensure_teacher_access(user: User, teacher_id: int) -> None:
    if not is_admin(user) and user.teacher_id != teacher_id:
        raise HTTPException(
            status_code=403, detail="Solo puedes consultar tu propio registro docente"
        )


def ensure_section_access(
    db: Session, user: User, section_id: int, allow_student: bool = False
) -> Section:
    section = db.get(Section, section_id)
    if section is None:
        raise HTTPException(status_code=404, detail="No se encontró la sección")
    if is_admin(user) or user.teacher_id == section.teacher_id:
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
    raise HTTPException(status_code=403, detail="Esta sección está fuera de tu ámbito académico")


def ensure_enrollment_access(db: Session, user: User, enrollment_id: int) -> Enrollment:
    enrollment = db.get(Enrollment, enrollment_id)
    if enrollment is None:
        raise HTTPException(status_code=404, detail="No se encontró la selección")
    if (
        is_admin(user)
        or user.student_id == enrollment.student_id
        or user.teacher_id == enrollment.section.teacher_id
    ):
        return enrollment
    raise HTTPException(status_code=403, detail="Esta selección está fuera de tu ámbito académico")
