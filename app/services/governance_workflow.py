"""Serialized administrative actions and audit without invented legacy history."""

from sqlalchemy import update

from app.models.configuration_model import GovernanceControl
from app.models.security_model import AuditLog
from app.models.user_model import User
from app.services.academic_grading import audit_event


def lock_governance(db):
    if db.get(GovernanceControl, 1) is None:
        db.add(GovernanceControl(governance_control_id=1, version=0))
        db.flush()
    db.execute(
        update(GovernanceControl)
        .where(GovernanceControl.governance_control_id == 1)
        .values(version=GovernanceControl.version + 1)
    )
    db.expire_all()


def record(db, user, action, resource, detail):
    audit_event(db, user.user_id, action, resource, detail)


def history(db, resource):
    return [
        {
            "id": a.audit_log_id,
            "action": a.action,
            "detail": a.detail,
            "created_at": a.created_at,
            "actor": db.get(User, a.user_id).username
            if a.user_id and db.get(User, a.user_id)
            else "Registro anterior",
        }
        for a in db.query(AuditLog)
        .filter_by(resource=resource)
        .order_by(AuditLog.audit_log_id.desc())
    ]
