"""Platform super administration (Fase 4, block B)."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.database import settings
from app.db.Session import get_db
from app.models.billing_model import Plan
from app.models.institution_model import Institution
from app.models.platform_model import PlatformAdmin, PlatformAuditLog
from app.pagination import page_query, search
from app.schemas.platform_schema import (
    InstitutionCreate,
    InstitutionOut,
    InstitutionStatusChange,
    PlanCreate,
    PlanFields,
    PlanOut,
    PlatformAuditOut,
    PlatformLogin,
    PlatformMe,
    PlatformToken,
    PublicInstitution,
    SubscriptionChange,
)
from app.schemas.support_schema import PlatformTicketOut
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
        "subscription": service.subscription_out(db, institution.institution_id),
        "purge_available_on": service.purge_available_on(institution),
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


@router.put("/platform/institutions/{institution_id}/subscription", response_model=InstitutionOut)
def change_subscription(
    institution_id: int,
    data: SubscriptionChange,
    db: Session = Depends(get_db),
    admin: PlatformAdmin = Depends(require_platform_admin),
):
    service.lock_platform(db)
    institution = service.institution_or_404(db, institution_id)
    service.change_subscription(db, institution, data, admin)
    db.commit()
    return institution_out(db, institution)


class PurgeRequest(BaseModel):
    code: str = Field(min_length=3, max_length=60)
    reason: str = Field(min_length=5, max_length=250)


@router.post("/platform/institutions/{institution_id}/purge")
def purge_institution(
    institution_id: int,
    data: PurgeRequest,
    db: Session = Depends(get_db),
    admin: PlatformAdmin = Depends(require_platform_admin),
):
    """Irreversible: deletes every record and file of the institution (90 days after it stopped)."""
    service.lock_platform(db)
    institution = service.institution_or_404(db, institution_id)
    deleted = service.purge_institution(db, institution, data.code, data.reason, admin)
    db.commit()
    return {"status": institution.status, "deleted_rows": deleted}


class SupportReply(BaseModel):
    body: str = Field(default="", max_length=5000)
    status: str = Field(pattern=r"^(open|in_progress|waiting|resolved|closed)$")


@router.get("/platform/support", response_model=list[PlatformTicketOut])
def support_inbox(
    response: Response,
    status: str | None = Query(None, pattern=r"^(open|in_progress|waiting|resolved|closed)$"),
    q: str | None = Query(None, max_length=60),
    skip: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin: PlatformAdmin = Depends(require_platform_admin),
):
    from app.models.support_model import SupportTicket
    from app.services.support import ticket_out

    query = db.query(SupportTicket).order_by(SupportTicket.updated_at.desc())
    if status:
        query = query.filter(SupportTicket.status == status)
    query = search(query, q, SupportTicket.subject, SupportTicket.requester_name)
    rows = page_query(query, response, skip, limit)
    ids = {ticket.institution_id for ticket in rows}
    names = dict(
        db.query(Institution.institution_id, Institution.name).filter(
            Institution.institution_id.in_(ids)
        )
    )
    return [ticket_out(t) | {"institution": names.get(t.institution_id, "")} for t in rows]


@router.get("/platform/support/{ticket_id}", response_model=PlatformTicketOut)
def support_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    _admin: PlatformAdmin = Depends(require_platform_admin),
):
    from app.models.support_model import SupportTicket
    from app.services.support import ticket_out

    ticket = db.get(SupportTicket, ticket_id)
    if ticket is None:
        raise HTTPException(404, "Ticket no encontrado")
    institution = db.get(Institution, ticket.institution_id)
    return ticket_out(ticket, with_messages=True) | {
        "institution": institution.name if institution else "",
        "requester_email": ticket.requester_email,
    }


@router.post("/platform/support/{ticket_id}/reply", response_model=PlatformTicketOut)
def support_reply(
    ticket_id: int,
    data: SupportReply,
    db: Session = Depends(get_db),
    admin: PlatformAdmin = Depends(require_platform_admin),
):
    """Answer (emails the person who opened it) or only change the status."""
    from app.models.support_model import SupportTicket
    from app.services.support import team_reply, ticket_out

    service.lock_platform(db)
    ticket = db.get(SupportTicket, ticket_id)
    if ticket is None:
        raise HTTPException(404, "Ticket no encontrado")
    if data.body.strip():
        team_reply(db, ticket, admin, data.body, data.status)
    else:
        ticket.status = data.status
        ticket.updated_at = service.now()
    service.platform_record(
        db,
        admin,
        "support.answered" if data.body.strip() else "support.status",
        f"support:{ticket_id}",
        f"Estado: {data.status}",
    )
    db.commit()
    return ticket_out(ticket, with_messages=True)


@router.get("/platform/plans", response_model=list[PlanOut])
def list_plans(
    db: Session = Depends(get_db), _admin: PlatformAdmin = Depends(require_platform_admin)
):
    plans = db.query(Plan).order_by(Plan.sort_order, Plan.plan_id).all()
    return [service.plan_fields(plan) for plan in plans]


@router.post("/platform/plans", response_model=PlanOut)
def create_plan(
    data: PlanCreate,
    db: Session = Depends(get_db),
    admin: PlatformAdmin = Depends(require_platform_admin),
):
    service.lock_platform(db)
    plan = service.create_plan(db, data, admin)
    db.commit()
    return service.plan_fields(plan)


@router.put("/platform/plans/{code}", response_model=PlanOut)
def update_plan(
    code: str,
    data: PlanFields,
    db: Session = Depends(get_db),
    admin: PlatformAdmin = Depends(require_platform_admin),
):
    service.lock_platform(db)
    plan = service.update_plan(db, service.plan_by_code(db, code), data, admin)
    db.commit()
    return service.plan_fields(plan)


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
