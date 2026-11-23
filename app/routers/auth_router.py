import hmac
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Cookie,
    Depends,
    Header,
    HTTPException,
    Request,
    Response,
    status,
)
from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session

from app.auth import (
    SUSPENDED_MESSAGE,
    account_is_active,
    ensure_account_active,
    ensure_institution_open,
    get_current_user,
)
from app.db.database import settings
from app.db.Session import get_db
from app.db.tenant import DEFAULT_INSTITUTION_ID, set_tenant, tenant_bypass
from app.models.institution_model import Institution
from app.models.role_model import Role
from app.models.security_model import RefreshToken
from app.models.user_model import User
from app.repositories.user_repository import create_user
from app.routers.dashboard_router import display_name
from app.schemas.auth_schema import (
    BootstrapRequest,
    ChangePasswordRequest,
    LoginRequest,
    MfaDisableRequest,
    MfaEnableRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    TokenOut,
)
from app.schemas.user_schema import EmailPreferences, UserCreate, UserOut
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
from app.services.email_service import deliver_after_commit, queue_email
from app.services.email_templates import app_link, password_reset
from app.services.login_throttle import ensure_not_blocked, record_failure, record_success
from app.services.one_time_tokens import INVALID_LINK, consume_token, issue_token
from app.services.permission_catalog import grant_system_defaults
from app.services.rate_limit import client_ip
from app.services.tenant_host import institution_for_host

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
    access_token = create_access_token(user.user_id, user.session_version, user.institution_id)
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
    if db.query(User).execution_options(**tenant_bypass()).first() is not None:
        raise HTTPException(status_code=409, detail="La configuración inicial ya se completó")
    # The first administrator belongs to the first institution (Fase 4 A).
    set_tenant(db, DEFAULT_INSTITUTION_ID)
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


def ensure_code_open(db: Session, code: str | None) -> None:
    """A suspended institution says so at sign-in instead of «wrong password»."""
    if not code:
        return
    institution = db.query(Institution).filter(Institution.slug == code.strip().casefold()).first()
    if institution is not None and institution.status != "active":
        raise HTTPException(status_code=403, detail=SUSPENDED_MESSAGE)


AMBIGUOUS_ACCOUNT = "Esa cuenta existe en varias instituciones. Indica el código de tu institución"


def account_institution(db: Session, condition, code: str | None, ambiguous="raise"):
    """Institution of the account matching ``condition`` (Fase 4 A).

    With an institution code it is that institution (if active). Without one,
    the account must exist in a single institution; otherwise sign-in asks for
    the code and password reset silently does nothing. ``None``: unknown.
    """
    if code:
        institution = (
            db.query(Institution).filter(Institution.slug == code.strip().casefold()).first()
        )
        if institution is None or institution.status != "active":
            return None
        return institution.institution_id
    found = {
        row[0]
        for row in db.query(User.institution_id)
        .filter(condition)
        .execution_options(**tenant_bypass())
        .limit(3)
    }
    if len(found) > 1:
        if ambiguous == "raise":
            raise HTTPException(status_code=409, detail=AMBIGUOUS_ACCOUNT)
        return None
    if not found:
        return None
    institution_id = found.pop()
    status_value = db.get(Institution, institution_id).status
    return institution_id if status_value == "active" else None


# Parallel tabs may refresh with the same cookie within this window.
REUSE_GRACE = timedelta(seconds=30)

# Compared against when the account does not exist, so the response time does
# not reveal which usernames are registered.
_DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(16))


@router.post("/login", response_model=TokenOut)
def login(data: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = client_ip(request)
    ensure_not_blocked(db, ip, data.username)
    # Fase 4 B: at an institution's own address its code comes from the host.
    addressed = institution_for_host(db, request)
    code = addressed.slug if addressed is not None else data.institution
    ensure_code_open(db, code)
    institution_id = account_institution(
        db,
        or_(User.username == data.username, User.email == data.username),
        code,
    )
    user = None
    if institution_id is not None:
        set_tenant(db, institution_id)
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
        if institution_id is not None:
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
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == hash_token(refresh_token))
        .execution_options(**tenant_bypass())
        .first()
    )
    if session is None:
        raise HTTPException(status_code=401, detail="La sesión expiró. Inicia sesión de nuevo")
    set_tenant(db, session.institution_id)
    ensure_institution_open(db, session.institution_id)
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
            .execution_options(**tenant_bypass())
            .first()
        )
        if session is not None:
            set_tenant(db, session.institution_id)
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


RESET_ACCEPTED = (
    "Si la cuenta existe y tiene correo, enviamos un enlace para restablecer la contraseña"
)


@router.post("/password-reset/request", status_code=202)
def request_password_reset(
    data: PasswordResetRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Email a reset link. The answer is the same whether or not the account exists."""
    app_link("/")  # Same answer for every account when links cannot be built.
    ip, identifier = client_ip(request), data.identifier.strip()
    # Separate counter from sign-in: "reset:" keeps login attempts independent.
    ensure_not_blocked(db, ip, f"reset:{identifier}")
    record_failure(db, ip, f"reset:{identifier}")
    matches = or_(
        func.lower(User.username) == identifier.casefold(),
        func.lower(User.email) == identifier.casefold(),
    )
    institution_id = account_institution(db, matches, data.institution, ambiguous=None)
    user = None
    if institution_id is not None:
        set_tenant(db, institution_id)
        user = db.query(User).filter(matches).first()
    if user is not None and user.email and account_is_active(user):
        user = lock_account(db, user)
        token = issue_token(db, user.user_id, "reset")
        message = password_reset(db, display_name(db, user), token)
        queue_email(
            db,
            user.email,
            message.subject,
            message.text,
            message.html,
            category="security",
            user_id=user.user_id,
        )
        audit(db, "password.reset.requested", "user", user.user_id)
    db.commit()
    deliver_after_commit(background_tasks, db)
    return {"message": RESET_ACCEPTED}


@router.post("/password-reset/confirm", status_code=204)
def confirm_password_reset(data: PasswordResetConfirm, db: Session = Depends(get_db)):
    """Set a new password from a reset or invitation link; every session is closed."""
    token = consume_token(db, data.token, ("reset", "invite"))
    set_tenant(db, token.institution_id)
    user = db.get(User, token.user_id)
    if user is None or not account_is_active(user):
        raise HTTPException(400, INVALID_LINK)
    user = lock_account(db, user)
    user.password = hash_password(data.new_password)
    revoke_account_sessions(db, user)
    audit(
        db,
        "account.activated" if token.purpose == "invite" else "password.reset.completed",
        "user",
        user.user_id,
    )
    db.commit()


@router.get("/email-preferences", response_model=EmailPreferences)
def email_preferences(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/email-preferences", response_model=EmailPreferences)
def update_email_preferences(
    data: EmailPreferences,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Turn email notices on or off; security emails are always sent."""
    user = lock_account(db, current_user)
    changed = []
    for key, value in data.model_dump().items():
        if getattr(user, key) != value:
            changed.append(f"{key}: {'sí' if value else 'no'}")
            setattr(user, key, value)
    audit(db, "email.preferences.updated", "user", user.user_id, "; ".join(changed))
    db.commit()
    return user
