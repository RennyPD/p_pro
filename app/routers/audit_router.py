from datetime import UTC, date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.auth import require_permissions
from app.db.Session import get_db
from app.models.security_model import AuditLog
from app.models.user_model import User
from app.pagination import page_query
from app.schemas.audit_schema import AuditLogOut
from app.services.business_time import INSTITUTION_TIME_ZONE

router = APIRouter(
    prefix="/audit",
    tags=["audit"],
    dependencies=[Depends(require_permissions("audit.view"))],
)


@router.get("/", response_model=list[AuditLogOut])
def list_audit_logs(
    response: Response,
    action: str | None = None,
    resource: str | None = None,
    user_id: int | None = Query(None, ge=1),
    start: date | None = None,
    end: date | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    if start and end and start > end:
        raise HTTPException(422, "La fecha inicial debe ser anterior o igual a la fecha final")
    query = db.query(AuditLog, User.username).outerjoin(User, AuditLog.user_id == User.user_id)
    if action:
        query = query.filter(AuditLog.action == action)
    if resource and resource.strip():
        query = query.filter(AuditLog.resource.icontains(resource.strip(), autoescape=True))
    if user_id is not None:
        query = query.filter(AuditLog.user_id == user_id)
    if start is not None:
        query = query.filter(AuditLog.created_at >= local_midnight_utc(start))
    if end is not None and end < date.max:
        query = query.filter(AuditLog.created_at < local_midnight_utc(end + timedelta(days=1)))
    rows = page_query(
        query.order_by(AuditLog.created_at.desc(), AuditLog.audit_log_id.desc()),
        response,
        skip,
        limit,
    )
    result = []
    for entry, username in rows:
        item = AuditLogOut.model_validate(entry)
        item.actor = username
        item.created_at = item.created_at.replace(tzinfo=UTC)
        if entry.resource == "authentication" or entry.action.startswith(("password.", "mfa.")):
            item.detail = ""
        result.append(item)
    return result


def local_midnight_utc(day: date) -> datetime:
    return (
        datetime.combine(day, time.min, tzinfo=INSTITUTION_TIME_ZONE)
        .astimezone(UTC)
        .replace(tzinfo=None)
    )
