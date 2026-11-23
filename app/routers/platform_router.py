"""Platform super administration (Fase 4, block B)."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.database import settings
from app.db.Session import get_db
from app.models.institution_model import Institution
from app.models.platform_model import PlatformAdmin, PlatformAuditLog
from app.pagination import page_query, search
from app.schemas.platform_schema import (
    InstitutionCreate,
    InstitutionOut,
    InstitutionStatusChange,
    PlatformAuditOut,
    PlatformLogin,
    PlatformMe,
    PlatformToken,
    PublicInstitution,
)
from app.security import create_access_token, decode_token_claims
from app.services import platform as service
from app.services.email_service import deliver_after_commit
from app.services.rate_limit import PLATFORM_LOGIN, PUBLIC, per_address
from app.services.tenant_host import institution_for_host

router = APIRouter(tags=["platform"])
bearer = HTTPBearer(auto_error=False)


def require_platform_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> PlatformAdmin:
    """Only a platform token opens these routes; an institution token never does."""
    if credentials is None:
        raise HTTPException(401, "Debes iniciar sesión en la plataforma")
    claims = decode_token_claims(credentials.credentials)
    if claims.get("scp") != "platform":
        raise HTTPException(403, "Esta sesión no es de la plataforma")
    admin = db.get(PlatformAdmin, int(claims["sub"]))
    if admin is None or not admin.active or admin.session_version != int(claims.get("sv", 0)):
        raise HTTPException(401, "La sesión de la plataforma no es válida")
    return admin


def institution_out(db: Session, institution: Institution) -> dict:
    domain = settings.tenant_base_domain
    return {
        "institution_id": institution.institution_id,
        "name": institution.name,
        "code": institution.slug,
        "status": institution.status,
        "contact_email": institution.contact_email,
        "status_reason": institution.status_reason,
        "status_changed_at": institution.status_changed_at,
        "created_at": institution.created_at,
        "usage": service.usage(db, institution.institution_id),
        "address": f"https://{institution.slug}.{domain}" if domain else None,
    }


@router.post(
    "/platform/auth/login",
    response_model=PlatformToken,
    dependencies=[Depends(per_address(PLATFORM_LOGIN))],
)
def platform_login(data: PlatformLogin, db: Session = Depends(get_db)):
    service.lock_platform(db)
    admin = service.authenticate(db, data.email, data.password, data.otp)
    db.commit()
    token = create_access_token(admin.platform_admin_id, admin.session_version, scope="platform")
    return {"access_token": token, "name": admin.name, "email": admin.email}


@router.get("/platform/me", response_model=PlatformMe)
def platform_me(admin: PlatformAdmin = Depends(require_platform_admin)):
    return admin


@router.get("/platform/institutions", response_model=list[InstitutionOut])
def list_institutions(
    response: Response,
    q: str | None = None,
    status: str | None = Query(None, pattern="^(active|suspended)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin: PlatformAdmin = Depends(require_platform_admin),
):
    query = search(db.query(Institution), q, Institution.name, Institution.slug)
    if status:
        query = query.filter(Institution.status == status)
    rows = page_query(query.order_by(Institution.name), response, skip, limit)
    return [institution_out(db, item) for item in rows]


@router.post("/platform/institutions", response_model=InstitutionOut)
def create_institution(
    data: InstitutionCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    admin: PlatformAdmin = Depends(require_platform_admin),
):
    service.lock_platform(db)
    institution, _first_admin = service.create_institution(db, data, admin)
    db.commit()
    deliver_after_commit(background_tasks, db)  # the first administrator's invitation
    return institution_out(db, institution)


@router.post("/platform/institutions/{institution_id}/suspend", response_model=InstitutionOut)
def suspend_institution(
    institution_id: int,
    data: InstitutionStatusChange,
    db: Session = Depends(get_db),
    admin: PlatformAdmin = Depends(require_platform_admin),
):
    service.lock_platform(db)
    institution = service.institution_or_404(db, institution_id)
    service.change_status(db, institution, "suspended", data.reason, admin)
    db.commit()
    return institution_out(db, institution)


@router.post("/platform/institutions/{institution_id}/reactivate", response_model=InstitutionOut)
def reactivate_institution(
    institution_id: int,
    data: InstitutionStatusChange,
    db: Session = Depends(get_db),
    admin: PlatformAdmin = Depends(require_platform_admin),
):
    service.lock_platform(db)
    institution = service.institution_or_404(db, institution_id)
    service.change_status(db, institution, "active", data.reason, admin)
    db.commit()
    return institution_out(db, institution)


@router.get("/platform/audit", response_model=list[PlatformAuditOut])
def platform_audit(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin: PlatformAdmin = Depends(require_platform_admin),
):
    query = db.query(PlatformAuditLog).order_by(PlatformAuditLog.platform_audit_log_id.desc())
    rows = page_query(query, response, skip, limit)
    actors = {a.platform_admin_id: a.email for a in db.query(PlatformAdmin)}
    return [
        {
            "platform_audit_log_id": row.platform_audit_log_id,
            "actor": actors.get(row.platform_admin_id),
            "action": row.action,
            "resource": row.resource,
            "detail": row.detail,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.get(
    "/public/institution",
    response_model=PublicInstitution,
    dependencies=[Depends(per_address(PUBLIC))],
)
def public_institution(request: Request, code: str | None = None, db: Session = Depends(get_db)):
    """Name of the institution addressed by the host (or by its code) for the sign-in page."""
    institution = institution_for_host(db, request)
    if institution is None and code:
        institution = (
            db.query(Institution).filter(Institution.slug == code.strip().casefold()).first()
        )
    if institution is None:
        raise HTTPException(404, "Institución no encontrada")
    return {"code": institution.slug, "name": institution.name, "status": institution.status}
