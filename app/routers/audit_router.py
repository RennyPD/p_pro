from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import require_permissions
from app.db.Session import get_db
from app.models.security_model import AuditLog
from app.schemas.audit_schema import AuditLogOut

router = APIRouter(
    prefix="/audit",
    tags=["audit"],
    dependencies=[Depends(require_permissions("reports.view", fallback_roles=("admin",)))],
)


@router.get("/", response_model=list[AuditLogOut])
def list_audit_logs(
    action: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(AuditLog).order_by(AuditLog.created_at.desc())
    if action:
        query = query.filter(AuditLog.action == action)
    return query.offset(skip).limit(limit).all()
