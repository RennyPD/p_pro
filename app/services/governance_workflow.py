"""Serialized administrative actions and audit without invented legacy history."""

from app.models.security_model import AuditLog
from app.models.user_model import User
from app.services.academic_grading import audit_event
from app.services.write_locks import lock_scope


def lock_governance(db):
    """Academic write domain (see app/services/write_locks.py)."""
    lock_scope(db, "academic")


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
