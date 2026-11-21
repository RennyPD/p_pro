import hmac
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from app.auth import account_is_active, ensure_account_active, get_current_user
from app.db.database import settings
from app.db.Session import get_db
from app.models.role_model import Role
from app.models.security_model import RefreshToken
from app.models.user_model import User
from app.repositories.user_repository import create_user
from app.schemas.auth_schema import (
    BootstrapRequest,
    ChangePasswordRequest,
    LoginRequest,
    MfaDisableRequest,
    MfaEnableRequest,
    TokenOut,
)
from app.schemas.user_schema import UserCreate, UserOut
from app.security import (
    create_access_token,
    create_refresh_token,
    create_totp_secret,
    hash_password,
    hash_token,
    totp_step,
    verify_password,
)
from app.services.account_sessions import lock_account, revoke_account_sessions
from app.services.audit_log import audit_event
from app.services.login_throttle import ensure_not_blocked, record_failure, record_success
from app.services.permission_catalog import grant_system_defaults

router = APIRouter(prefix="/auth", tags=["authentication"])


def audit(db: Session, action: str, resource: str, user_id: int | None = None, detail: str = ""):
    audit_event(db, user_id, action, resource, detail)


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
    access_token = create_access_token(user.user_id, user.session_version)
    db.commit()
    response.set_cookie(
        "refresh_token",
        raw,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path="/auth",
    )
    return TokenOut(access_token=access_token, user=user)


def ensure_bootstrap_allowed(provided: str | None) -> None:
    """In production the first administrator needs BOOTSTRAP_TOKEN (audit, low finding)."""
    expected = settings.bootstrap_token
    if expected:
        if not provided or not hmac.compare_digest(provided, expected):
            raise HTTPException(403, "El código de configuración inicial no es válido")
        return
    if settings.app_environment == "production":
        raise HTTPException(
            403,
            "La configuración inicial está deshabilitada. Define BOOTSTRAP_TOKEN en el servidor",
        )


@router.post("/bootstrap", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def bootstrap_admin(
    data: BootstrapRequest,
    response: Response,
    db: Session = Depends(get_db),
    bootstrap_token: str | None = Header(default=None, alias="X-Bootstrap-Token"),
):
    ensure_bootstrap_allowed(bootstrap_token)
    # Serialize the initial account check even when the users table is empty.
    if db.get_bind().dialect.name == "sqlite":
        db.execute(text("BEGIN IMMEDIATE"))
    else:
        db.execute(text("LOCK TABLE users IN SHARE ROW EXCLUSIVE MODE"))
    if db.query(User).first() is not None:
        raise HTTPException(status_code=409, detail="La configuración inicial ya se completó")
    role = db.query(Role).filter(Role.name.ilike("admin")).first()
    if role is None:
        role = Role(name="admin", description="System administrator")
        db.add(role)
        db.flush()
    # Fresh installations get the whole permission catalog for the first administrator.
    grant_system_defaults(db, role)
    user_data = UserCreate(**data.model_dump(), role_id=role.role_id)
    user = create_user(db, user_data)
    audit(db, "account.bootstrapped", f"user:{user.user_id}", user.user_id, "Primer administrador")
    return issue_session(db, response, user)


# Parallel tabs may refresh with the same cookie within this window.
REUSE_GRACE = timedelta(seconds=30)

# Compared against when the account does not exist, so the response time does
# not reveal which usernames are registered.
_DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(16))


def client_ip(request: Request) -> str:
    # Behind a proxy, run uvicorn with --proxy-headers and FORWARDED_ALLOW_IPS.
    return request.client.host if request.client else "desconocida"


@router.post("/login", response_model=TokenOut)
def login(data: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = client_ip(request)
    ensure_not_blocked(db, ip, data.username)
    user = (
        db.query(User)
        .filter(or_(User.username == data.username, User.email == data.username))
        .first()
    )
    if user is not None:
        user = lock_account(db, user)
    valid = verify_password(data.password, user.password if user else _DUMMY_PASSWORD_HASH)
    if user is None or not valid:
        record_failure(db, ip, data.username)
        audit(db, "login.failed", "authentication", user.user_id if user else None)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.mfa_enabled:
        check_mfa_attempt(
            db,
            user,
            bool(user.mfa_secret and data.otp and consume_totp(user, data.otp)),
            status_code=401,
        )
    record_success(db, ip, data.username)
    if not account_is_active(user):
        # Only reported after valid credentials, so it does not reveal accounts.
        audit(db, "login.inactive", "authentication", user.user_id)
        db.commit()
        ensure_account_active(user, status_code=403)
    return issue_session(db, response, user)


@router.post("/refresh", response_model=TokenOut)
def refresh_session(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
):
    if not refresh_token:
        raise HTTPException(
            status_code=401, detail="No se encontró la sesión. Inicia sesión de nuevo"
        )
    session = (
        db.query(RefreshToken).filter(RefreshToken.token_hash == hash_token(refresh_token)).first()
    )
    if session is None:
        raise HTTPException(status_code=401, detail="La sesión expiró. Inicia sesión de nuevo")
    user = db.get(User, session.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="La cuenta ya no existe")
    user = lock_account(db, user)
    db.refresh(session)
    now = datetime.now(UTC).replace(tzinfo=None)
    if session.rotated_at is not None and session.rotated_at < now - REUSE_GRACE:
        # A rotated token came back: someone else may hold a copy. Close everything.
        revoke_account_sessions(db, user)
        audit(db, "session.reuse_detected", "authentication", user.user_id)
        db.commit()
        raise HTTPException(
            status_code=401,
            detail="Detectamos un uso repetido de la sesión. Inicia sesión de nuevo",
        )
    if session.revoked_at is not None or session.expires_at <= now:
        raise HTTPException(status_code=401, detail="La sesión expiró. Inicia sesión de nuevo")
    session.revoked_at = session.rotated_at = now
    if not account_is_active(user):
        db.commit()
        ensure_account_active(user)
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
    response.delete_cookie("refresh_token", path="/auth", secure=settings.secure_cookies)


@router.get("/sessions")
def list_sessions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    now = datetime.now(UTC).replace(tzinfo=None)
    return [
        {
            "session_id": item.refresh_token_id,
            "created_at": item.created_at.replace(tzinfo=UTC),
            "expires_at": item.expires_at.replace(tzinfo=UTC),
            "active": item.revoked_at is None and item.expires_at > now,
        }
        for item in db.query(RefreshToken)
        .filter(RefreshToken.user_id == current_user.user_id)
        .order_by(RefreshToken.created_at.desc())
        .all()
    ]


@router.post("/sessions/revoke-all", status_code=204)
def revoke_all_sessions(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user = lock_account(db, current_user)
    revoke_account_sessions(db, current_user)
    audit(db, "sessions.revoked_all", "authentication", current_user.user_id)
    db.commit()
    response.delete_cookie("refresh_token", path="/auth", secure=settings.secure_cookies)


@router.post("/change-password", status_code=204)
def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user = lock_account(db, current_user)
    if not verify_password(data.current_password, current_user.password):
        raise HTTPException(status_code=400, detail="La contraseña actual es incorrecta")
    current_user.password = hash_password(data.new_password)
    revoke_account_sessions(db, current_user)
    audit(db, "password.changed", "user", current_user.user_id)
    db.commit()


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


def consume_totp(user: User, code: str) -> bool:
    """Accept a code for the account's secret once; replays of a used step fail."""
    step = totp_step(user.mfa_secret, code)
    if step is None or (user.mfa_last_step is not None and step <= user.mfa_last_step):
        return False
    user.mfa_last_step = step
    return True


def check_mfa_attempt(db: Session, user: User, valid: bool, *, status_code: int = 400):
    now = datetime.now(UTC).replace(tzinfo=None)
    if user.mfa_attempt_window is None or user.mfa_attempt_window <= now:
        user.mfa_attempt_window = now + timedelta(minutes=5)
        user.mfa_attempts = 0
    if user.mfa_attempts >= 5:
        raise HTTPException(429, "Se agotaron los intentos de verificación. Espera cinco minutos")
    if not valid:
        user.mfa_attempts += 1
        audit(db, "mfa.verification_failed", "authentication", user.user_id)
        db.commit()
        raise HTTPException(status_code, "Verifica tus credenciales y el código de seis dígitos")
    user.mfa_attempts = 0
    user.mfa_attempt_window = None


@router.post("/mfa/setup")
def setup_mfa(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user = lock_account(db, current_user)
    secret = create_totp_secret()
    current_user.mfa_pending_secret = secret
    current_user.mfa_pending_until = datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=10)
    audit(db, "mfa.setup_started", "authentication", current_user.user_id)
    label = quote(current_user.email, safe="")
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return {
        "secret": secret,
        "otpauth_uri": f"otpauth://totp/Nexo:{label}?secret={secret}&issuer=Nexo",
    }


@router.delete("/mfa/setup", status_code=204)
def cancel_mfa_setup(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current_user = lock_account(db, current_user)
    if current_user.mfa_pending_secret:
        current_user.mfa_pending_secret = None
        current_user.mfa_pending_until = None
        audit(db, "mfa.setup_cancelled", "authentication", current_user.user_id)
    db.commit()


@router.post("/mfa/enable", status_code=204)
def enable_mfa(
    data: MfaEnableRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user = lock_account(db, current_user)
    secret = current_user.mfa_pending_secret
    expires = current_user.mfa_pending_until
    if not secret or not expires or expires <= datetime.now(UTC).replace(tzinfo=None):
        raise HTTPException(409, "La configuración venció. Genera una clave nueva")
    replacing = current_user.mfa_enabled
    verified = verify_password(data.current_password, current_user.password) and (
        not replacing
        or bool(
            data.current_code
            and current_user.mfa_secret
            and consume_totp(current_user, data.current_code)
        )
    )
    new_step = totp_step(secret, data.code)
    check_mfa_attempt(db, current_user, bool(verified and new_step is not None))
    current_user.mfa_secret = secret
    current_user.mfa_last_step = new_step
    current_user.mfa_enabled = True
    revoke_account_sessions(db, current_user)
    audit(
        db, "mfa.replaced" if replacing else "mfa.enabled", "authentication", current_user.user_id
    )
    db.commit()


@router.post("/mfa/disable", status_code=204)
def disable_mfa(
    data: MfaDisableRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user = lock_account(db, current_user)
    if not current_user.mfa_enabled or not current_user.mfa_secret:
        raise HTTPException(409, "La verificación en dos pasos ya está desactivada")
    verified = verify_password(data.current_password, current_user.password) and bool(
        current_user.mfa_secret and consume_totp(current_user, data.code)
    )
    check_mfa_attempt(db, current_user, verified)
    current_user.mfa_enabled = False
    current_user.mfa_secret = None
    revoke_account_sessions(db, current_user)
    audit(db, "mfa.disabled", "authentication", current_user.user_id)
    db.commit()
