from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db.Session import get_db
from app.models.role_model import Role
from app.models.security_model import AuditLog, RefreshToken
from app.models.user_model import User
from app.repositories.user_repository import create_user
from app.schemas.auth_schema import BootstrapRequest, ChangePasswordRequest, LoginRequest, TokenOut
from app.schemas.user_schema import UserCreate, UserOut
from app.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["authentication"])
login_attempts: dict[str, deque[datetime]] = defaultdict(deque)


def audit(db: Session, action: str, resource: str, user_id: int | None = None, detail: str = ""):
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            resource=resource,
            detail=detail,
            created_at=datetime.now(UTC).replace(tzinfo=None),
        )
    )


def issue_session(db: Session, response: Response, user: User) -> TokenOut:
    raw, digest, expires = create_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.user_id,
            token_hash=digest,
            expires_at=expires,
            created_at=datetime.now(UTC).replace(tzinfo=None),
        )
    )
    audit(db, "session.created", "authentication", user.user_id)
    db.commit()
    response.set_cookie(
        "refresh_token",
        raw,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=7 * 24 * 60 * 60,
        path="/auth",
    )
    return TokenOut(access_token=create_access_token(user.user_id), user=user)


@router.post("/bootstrap", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def bootstrap_admin(data: BootstrapRequest, response: Response, db: Session = Depends(get_db)):
    if db.query(User).first() is not None:
        raise HTTPException(status_code=409, detail="Bootstrap has already been completed")
    role = db.query(Role).filter(Role.name.ilike("admin")).first()
    if role is None:
        role = Role(name="admin", description="System administrator")
        db.add(role)
        db.flush()
    user_data = UserCreate(**data.model_dump(exclude={"role_id"}), role_id=role.role_id)
    user = create_user(db, user_data)
    return issue_session(db, response, user)


@router.post("/login", response_model=TokenOut)
def login(data: LoginRequest, response: Response, db: Session = Depends(get_db)):
    now = datetime.now(UTC).replace(tzinfo=None)
    attempts = login_attempts[data.username.casefold()]
    while attempts and attempts[0] < now - timedelta(minutes=5):
        attempts.popleft()
    if len(attempts) >= 5:
        raise HTTPException(
            status_code=429, detail="Too many login attempts. Try again in a few minutes"
        )
    user = (
        db.query(User)
        .filter(or_(User.username == data.username, User.email == data.username))
        .first()
    )
    if user is None or not verify_password(data.password, user.password):
        attempts.append(now)
        audit(db, "login.failed", "authentication", detail=data.username)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    attempts.clear()
    return issue_session(db, response, user)


@router.post("/refresh", response_model=TokenOut)
def refresh_session(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
):
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh session not found")
    session = (
        db.query(RefreshToken).filter(RefreshToken.token_hash == hash_token(refresh_token)).first()
    )
    now = datetime.now(UTC).replace(tzinfo=None)
    if session is None or session.revoked_at is not None or session.expires_at <= now:
        raise HTTPException(status_code=401, detail="Refresh session expired")
    session.revoked_at = now
    user = db.get(User, session.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User no longer exists")
    return issue_session(db, response, user)


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
):
    if refresh_token:
        session = (
            db.query(RefreshToken)
            .filter(RefreshToken.token_hash == hash_token(refresh_token))
            .first()
        )
        if session and session.revoked_at is None:
            session.revoked_at = datetime.now(UTC).replace(tzinfo=None)
            audit(db, "session.revoked", "authentication", session.user_id)
            db.commit()
    response.delete_cookie("refresh_token", path="/auth")


@router.post("/change-password", status_code=204)
def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(data.current_password, current_user.password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    current_user.password = hash_password(data.new_password)
    db.query(RefreshToken).filter(
        RefreshToken.user_id == current_user.user_id, RefreshToken.revoked_at.is_(None)
    ).update({"revoked_at": datetime.now(UTC).replace(tzinfo=None)})
    audit(db, "password.changed", "user", current_user.user_id)
    db.commit()


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user
