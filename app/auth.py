from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.Session import get_db
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
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = decode_access_token(credentials.credentials)
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User no longer exists")
    return user


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


def is_admin(user: User) -> bool:
    return user.role.name.casefold() == "admin"


def ensure_student_access(user: User, student_id: int) -> None:
    if not is_admin(user) and user.student_id != student_id:
        raise HTTPException(status_code=403, detail="You can only access your own student record")


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
    raise HTTPException(status_code=403, detail="Student access is outside your academic scope")


def ensure_teacher_access(user: User, teacher_id: int) -> None:
    if not is_admin(user) and user.teacher_id != teacher_id:
        raise HTTPException(status_code=403, detail="You can only access your own teacher record")


def ensure_section_access(
    db: Session, user: User, section_id: int, allow_student: bool = False
) -> Section:
    section = db.get(Section, section_id)
    if section is None:
        raise HTTPException(status_code=404, detail="Section not found")
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
    raise HTTPException(status_code=403, detail="Section access is outside your academic scope")


def ensure_enrollment_access(db: Session, user: User, enrollment_id: int) -> Enrollment:
    enrollment = db.get(Enrollment, enrollment_id)
    if enrollment is None:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    if (
        is_admin(user)
        or user.student_id == enrollment.student_id
        or user.teacher_id == enrollment.section.teacher_id
    ):
        return enrollment
    raise HTTPException(status_code=403, detail="Enrollment access is outside your academic scope")
